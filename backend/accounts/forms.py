from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.text import slugify
from .models import Workspace, Product
import re


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=30, required=True, label="Nombre")
    company_name = forms.CharField(
        max_length=200, 
        required=True, 
        label="Nombre de la empresa",
        help_text="El subdominio se generará automáticamente. Ej: 'Mi Empresa SAC' → 'mi-empresa-sac'"
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        required=True,
        label="Selecciona el producto",
        empty_label="-- Selecciona un producto --"
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'email', 'username', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email ya está registrado")
        return email
    
    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name')
        
        # Generar subdominio automáticamente
        subdomain = slugify(company_name)
        
        # Validar longitud mínima
        if len(subdomain) < 3:
            raise forms.ValidationError("El nombre de la empresa es muy corto (mínimo 3 caracteres)")
        
        # Palabras reservadas
        reserved = ['www', 'app', 'api', 'admin', 'mail', 'ftp', 'smtp', 'pop', 'imap', 
                   'localhost', 'test', 'dev', 'staging', 'prod', 'demo']
        if subdomain in reserved:
            raise forms.ValidationError("Este nombre está reservado, por favor elige otro")
        
        # Verificar disponibilidad del subdominio
        product = self.cleaned_data.get('product')
        if product and Workspace.objects.filter(subdomain=subdomain, product=product).exists():
            raise forms.ValidationError(f"Ya existe una empresa con este nombre en {product.display_name}")
        
        return company_name
    
    def get_subdomain(self):
        """Genera el subdominio a partir del nombre de la empresa"""
        company_name = self.cleaned_data.get('company_name', '')
        return slugify(company_name)
