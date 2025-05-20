# accounts/forms.py


from django.shortcuts import render

from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import *

class UserRegisterForm(UserCreationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}))

    class Meta:
        model = User
        fields = ['username', 'email']

class UserUpdateForm(UserChangeForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']  # Add only what's needed

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        # Remove unwanted fields from being rendered
        if 'password' in self.fields:
            del self.fields['password']
        self.fields['first_name'].widget.attrs.update({'placeholder': 'First Name', 'class': 'form-control'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Last Name', 'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'placeholder': 'Email', 'class': 'form-control'})


class UserInfoForm(forms.ModelForm):
    phone = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Phone'}), required =False)
    address = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Address'}), required =False)
    city = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", 'placeholder': 'City'}), required =False)
    state = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", 'placeholder': 'State'}), required =False)
    zipcode = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Zip'}), required =False)
    country = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Country'}), required =False)

    class Meta:
        model = Profile
        fields = ['phone', 'address', 'city', 'state', 'zipcode', 'country']


class OTPVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6, required=True, label='Enter OTP')


class UserRoleUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['role']

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'address', 'city', 'state', 'zipcode', 'country']



class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label="Enter your email", max_length=254)

