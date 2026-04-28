import json
from decimal import Decimal
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from .models import Product, Sale, SaleItem, StockMovement, Profile, Business


@login_required
def create_sale(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    items = data.get('items')
    if not items:
        return JsonResponse({"error": "No items provided"}, status=400)

    try:
        profile = getattr(request.user, 'profile', None)
        business = profile.business if profile else None
        
        with transaction.atomic():
            sale = Sale.objects.create(business=business, total_amount=Decimal('0.00'), staff=request.user)
            total = Decimal('0.00')

            for item in items:
                try:
                    # Security: Ensure product belongs to the user's business
                    product = Product.objects.select_for_update().get(id=item['product_id'], business=business)
                except (KeyError, Product.DoesNotExist):
                    raise ValueError(f"Invalid product ID: {item.get('product_id')}")

                qty = item.get('quantity')
                try:
                    qty = int(qty)
                except (TypeError, ValueError):
                    raise ValueError("Invalid quantity")

                if qty <= 0:
                    raise ValueError("Invalid quantity")

                if product.quantity < qty:
                    raise ValueError("Insufficient stock")

                product.quantity -= qty
                product.save()

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    price=product.price,
                )

                StockMovement.objects.create(
                    business=business,
                    product=product,
                    quantity=qty,
                    movement_type="OUT",
                )

                total += product.price * qty

            sale.total_amount = total
            sale.save()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"message": "Sale completed", "total": float(total), "sale_id": sale.id})


@login_required
def dashboard(request):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None

    if not business:
        if request.user.is_superuser:
            return redirect('/api/platform-admin/')
        return HttpResponse("<h1>Access Denied</h1><p>Your account is not linked to any business.</p>", status=403)
    
    # Trial/subscription enforcement
    if business.subscription_plan == "trial" and business.trial_ends_at and business.trial_ends_at < now().date():
        business.is_active = False
        business.save(update_fields=["is_active"])

    if not business.is_active:
        return HttpResponse("<h1>Subscription Suspended</h1><p>Please contact support to reactivate your account.</p>", status=403)

    if business.subscription_plan == "trial" and business.trial_ends_at:
        days_left = (business.trial_ends_at - now().date()).days
        if days_left >= 0:
            if days_left == 0:
                messages.warning(request, "Your trial ends today. Subscribe to keep your store active.")
            elif days_left <= 3:
                messages.warning(request, f"Your trial ends in {days_left} day(s). Please subscribe soon.")
    
    total_products = Product.objects.filter(business=business).count()

    today_sales = Sale.objects.filter(
        business=business,
        created_at__date=now().date()
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    low_stock_count = Product.objects.filter(
        business=business,
        quantity__lte=F('low_stock_threshold')
    ).count()

    low_stock = Product.objects.filter(business=business, quantity__lte=F('low_stock_threshold'))
    recent_sales = Sale.objects.filter(business=business).order_by('-created_at')[:5]

    # Sales trend (last 7 days)
    sales_data = (
        Sale.objects.filter(business=business)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(total=Sum('total_amount'))
        .order_by('date')
    )

    dates = [str(item['date']) for item in sales_data]
    totals = [float(item['total']) if item['total'] else 0 for item in sales_data]

    # Top products
    top_products = (
        SaleItem.objects.filter(sale__business=business)
        .values('product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:5]
    )

    product_names = [item['product__name'] for item in top_products]
    product_quantities = [item['total_qty'] for item in top_products]

    return render(request, 'inventory/dashboard_new.html', {
        'total_products': total_products,
        'sales_today': today_sales,
        'low_stock_count': low_stock_count,
        'low_stock': low_stock,
        'recent_sales': recent_sales,
        'dates': json.dumps(dates),
        'totals': json.dumps(totals),
        'product_names': json.dumps(product_names),
        'product_quantities': json.dumps(product_quantities),
    })


@login_required
def pos_view(request):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return redirect('/api/dashboard/')
        
    products = Product.objects.filter(business=business)
    return render(request, 'inventory/pos_new.html', {'products': products})


@login_required
def product_list(request):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return redirect('/api/dashboard/')

    products = Product.objects.filter(business=business)
    return render(request, 'inventory/product_list.html', {'products': products})


@login_required
def sale_list(request):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return redirect('/api/dashboard/')

    sales = Sale.objects.filter(business=business).order_by('-created_at')
    return render(request, 'inventory/sale_list.html', {'sales': sales})


@login_required
def generate_receipt(request, sale_id):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return HttpResponse("Unauthorized", status=403)

    sale = get_object_or_404(Sale, id=sale_id, business=business)
    items = SaleItem.objects.filter(sale=sale)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{sale.id}.pdf"'

    doc = SimpleDocTemplate(response)
    styles = getSampleStyleSheet()

    elements = []

    # 🏪 Shop Name
    elements.append(Paragraph(f"{business.name} Receipt", styles['Title']))
    elements.append(Spacer(1, 10))

    # 🕒 Sale Info
    elements.append(Paragraph(f"Sale ID: {sale.id}", styles['Normal']))
    elements.append(Paragraph(f"Date: {sale.created_at}", styles['Normal']))
    elements.append(Spacer(1, 10))

    # 🛒 Items
    for item in items:
        line = f"{item.product.name} x{item.quantity} = ₦{item.price * item.quantity}"
        elements.append(Paragraph(line, styles['Normal']))

    elements.append(Spacer(1, 10))

    # 💰 Total
    elements.append(Paragraph(f"Total: ₦{sale.total_amount}", styles['Heading2']))

    doc.build(elements)

    return response


@login_required
def get_product_by_barcode(request, barcode):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    
    try:
        product = Product.objects.get(barcode=barcode, business=business)
        return JsonResponse({
            "id": product.id,
            "name": product.name,
            "price": float(product.price)
        })
    except Product.DoesNotExist:
            return JsonResponse({"error": "Product not found"}, status=404)


@login_required
def product_search(request):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    query = request.GET.get('q', '')
    
    if not business or not query:
        return JsonResponse([], safe=False)

    products = Product.objects.filter(
        business=business,
        name__icontains=query
    )[:10]
    results = [{"id": p.id, "name": p.name, "price": float(p.price)} for p in products]
    return JsonResponse(results, safe=False)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'barcode', 'price', 'quantity', 'low_stock_threshold']


class StaffForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text="Leave blank to keep current password")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_staff']


@staff_member_required
def product_upsert(request, pk=None):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return redirect('/api/dashboard/')

    product = get_object_or_404(Product, pk=pk, business=business) if pk else None
    
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            prod = form.save(commit=False)
            prod.business = business
            prod.save()
            return redirect('/api/products/')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {'form': form, 'product': product})


@staff_member_required
def staff_list(request):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return redirect('/api/dashboard/')

    # Filter users who have a profile linked to this business
    staffs = User.objects.filter(profile__business=business)
    return render(request, 'inventory/staff_list.html', {'staffs': staffs})


@staff_member_required
def staff_upsert(request, pk=None):
    profile = getattr(request.user, 'profile', None)
    business = profile.business if profile else None
    if not business:
        return redirect('/api/dashboard/')
    
    if pk:
        staff = get_object_or_404(User, pk=pk)
        # Verify the user belongs to this business
        if not Profile.objects.filter(user=staff, business=business).exists():
            return HttpResponse("Unauthorized", status=403)
    else:
        staff = None

    if request.method == "POST":
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_superuser = False
            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()
            
            if not pk:
                Profile.objects.create(user=user, business=business)
                
            return redirect('/api/staff/')
    else:
        form = StaffForm(instance=staff)
    return render(request, 'inventory/staff_form.html', {'form': form, 'staff': staff})


@staff_member_required
def admin_dashboard(request):
    return render(request, 'inventory/admin_dashboard.html')


class StoreOnboardingForm(forms.Form):
    business_name = forms.CharField(max_length=200)
    username = forms.CharField(max_length=150, help_text="Store Admin Username")
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    subscription_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))


class TrialRegistrationForm(forms.Form):
    business_name = forms.CharField(max_length=200)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


def register_trial(request):
    if request.user.is_authenticated:
        return redirect("/api/dashboard/")

    if request.method == "POST":
        form = TrialRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data["username"].strip(),
                    email=form.cleaned_data["email"].strip(),
                    password=form.cleaned_data["password"],
                    is_staff=True,
                )
                today = now().date()
                trial_end = today + timedelta(days=7)
                business = Business.objects.create(
                    name=form.cleaned_data["business_name"].strip(),
                    owner=user,
                    is_active=True,
                    subscription_plan="trial",
                    trial_started_at=today,
                    trial_ends_at=trial_end,
                    subscription_end=trial_end,
                )
                Profile.objects.create(user=user, business=business)

            messages.success(request, "Your 7-day trial is active. Please log in to continue.")
            return redirect("/accounts/login/")
    else:
        form = TrialRegistrationForm()

    return render(request, "inventory/register_trial.html", {"form": form})


@user_passes_test(lambda u: u.is_superuser)
def platform_admin_dashboard(request):
    businesses = Business.objects.all().order_by('-created_at')
    plan_catalog = [
        {
            "code": "starter_5000",
            "name": "Starter",
            "amount": 5000,
            "paystack_url": getattr(settings, "PAYSTACK_STARTER_URL", ""),
        },
        {
            "code": "growth_10000",
            "name": "Growth",
            "amount": 10000,
            "paystack_url": getattr(settings, "PAYSTACK_GROWTH_URL", ""),
        },
        {
            "code": "pro_20000",
            "name": "Pro",
            "amount": 20000,
            "paystack_url": getattr(settings, "PAYSTACK_PRO_URL", ""),
        },
    ]
    return render(request, 'inventory/platform_admin.html', {'businesses': businesses, "plan_catalog": plan_catalog})


@user_passes_test(lambda u: u.is_superuser)
def store_create(request):
    if request.method == "POST":
        form = StoreOnboardingForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create the Store Owner
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    is_staff=True # Allows them to manage their own store
                )
                # Create the Business
                business = Business.objects.create(
                    name=form.cleaned_data['business_name'],
                    owner=user,
                    subscription_end=form.cleaned_data['subscription_end'],
                    subscription_plan="trial",
                    trial_started_at=now().date(),
                    trial_ends_at=(now().date() + timedelta(days=7)),
                )
                # Link them
                Profile.objects.create(user=user, business=business)
            return redirect('/api/platform-admin/')
    else:
        form = StoreOnboardingForm()
    return render(request, 'inventory/store_form.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser)
def toggle_business_status(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    business.is_active = not business.is_active
    business.save()
    return redirect('/api/platform-admin/')


def send_trial_reminder_email(business):
    if not business.owner.email:
        return
    days_left = (business.trial_ends_at - now().date()).days
    if days_left < 0:
        return
    send_mail(
        subject="SmartStore Trial Reminder",
        message=(
            f"Hello {business.owner.username},\n\n"
            f"Your SmartStore trial for '{business.name}' ends in {days_left} day(s) "
            f"on {business.trial_ends_at}.\n"
            "Please subscribe to continue using your store without interruption.\n\n"
            "Plans: N5,000 / N10,000 / N20,000."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@smartstore.local"),
        recipient_list=[business.owner.email],
        fail_silently=True,
    )
