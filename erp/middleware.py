from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin


class GuestStockAccessMiddleware(MiddlewareMixin):
    """Misafirlerin ERP erişimini stok kartı görüntülemeyle sınırla."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match.namespace != 'erp' or not request.user.is_authenticated:
            return
        profile = getattr(request.user, 'userprofile', None)
        if profile and profile.is_misafir():
            if request.method not in ('GET', 'HEAD') or match.url_name not in ('stok_listesi', 'stok_detay'):
                raise PermissionDenied
