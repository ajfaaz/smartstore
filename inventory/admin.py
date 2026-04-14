from django.contrib import admin
from .models import Product, Sale, SaleItem, StockMovement

admin.site.register(Product)
admin.site.register(Sale)
admin.site.register(SaleItem)
admin.site.register(StockMovement)
