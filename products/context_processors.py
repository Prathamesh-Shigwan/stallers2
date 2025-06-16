from .models import CartItem, Cart, SiteContent
from .models import MainCategory


def cart_context(request):
    item_count = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            item_count = cart.cartitem_set.count()
        except Cart.DoesNotExist:
            item_count = 0
    return {'item_count': item_count}



def categories_processor(request):
    main_categories = MainCategory.objects.prefetch_related('subcategories').all().order_by('-id')
    return {
        'main_categories': main_categories,
    }


def site_content(request):
    try:
        content = SiteContent.objects.first()
    except SiteContent.DoesNotExist:
        content = None # Or create a default instance if preferred

    return {'site_content': content}