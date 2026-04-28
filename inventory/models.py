from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


SUBSCRIPTION_PLAN_CHOICES = [
    ("trial", "Trial"),
    ("starter_5000", "Starter - N5,000"),
    ("growth_10000", "Growth - N10,000"),
    ("pro_20000", "Pro - N20,000"),
]

class Business(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    subscription_end = models.DateField(null=True, blank=True)
    trial_started_at = models.DateField(null=True, blank=True)
    trial_ends_at = models.DateField(null=True, blank=True)
    last_trial_reminder_at = models.DateField(null=True, blank=True)
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLAN_CHOICES, default="trial")

    def __str__(self):
        return self.name

    @property
    def trial_days_left(self):
        if not self.trial_ends_at:
            return None
        return (self.trial_ends_at - timezone.localdate()).days

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="profiles", null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.business.name})"


class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Sale(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="sales", null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    staff = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        staff_name = self.staff.username if self.staff else "Unknown"
        return f"Sale #{self.pk} - {staff_name} - {self.created_at:%Y-%m-%d %H:%M:%S}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sale_items")
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ {self.price}"


class StockMovement(models.Model):
    MOVEMENT_IN = "IN"
    MOVEMENT_OUT = "OUT"
    MOVEMENT_TYPE_CHOICES = [
        (MOVEMENT_IN, "IN"),
        (MOVEMENT_OUT, "OUT"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="stock_movements", null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_movements")
    quantity = models.IntegerField()
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity} for {self.product.name}"
