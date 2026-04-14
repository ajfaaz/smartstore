from django.urls import path

from .views import create_sale, dashboard, pos_view, product_list, sale_list, generate_receipt, get_product_by_barcode, product_upsert, staff_list, staff_upsert, admin_dashboard, platform_admin_dashboard, store_create, toggle_business_status, product_search

urlpatterns = [
    path('sale/', create_sale),
    path('dashboard/', dashboard),
    path('pos/', pos_view),
    path('products/', product_list),
    path('sales/', sale_list),
    path('receipt/<int:sale_id>/', generate_receipt),
    path('product-by-barcode/<str:barcode>/', get_product_by_barcode),
    path('product-search/', product_search),
    path('admin-dashboard/', admin_dashboard),
    path('products/add/', product_upsert),
    path('products/edit/<int:pk>/', product_upsert),
    path('staff/', staff_list),
    path('staff/add/', staff_upsert),
    path('staff/edit/<int:pk>/', staff_upsert),
    path('platform-admin/', platform_admin_dashboard),
    path('platform-admin/add-store/', store_create),
    path('platform-admin/toggle-status/<int:business_id>/', toggle_business_status),
]
