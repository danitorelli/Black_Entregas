# cardapio_config/urls.py
from django.contrib import admin
from django.urls import path, include # Adicione 'include'
from django.conf import settings # Para servir arquivos de mídia em desenvolvimento
from django.conf.urls.static import static # Para servir arquivos de mídia em desenvolvimento

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('menu.urls')), # Inclui as URLs do app 'menu'
]

# Para servir arquivos de imagem (upload de produtos) em modo de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
