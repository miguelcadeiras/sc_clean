"""
License: MIT
Copyright (c) 2019 - present AppSeed.us
"""

from django.shortcuts import render

# Create your views here.
from django.contrib import messages

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.models import User
from django.forms.utils import ErrorList
from django.http import HttpResponse
from django.contrib.auth.forms import UserCreationForm



def login_view(request):
    msg = ''
    if request.method == "POST":

        username = request.POST['username']
        # print('username:',username)
        password = request.POST['password']
        # print('pass:',password)


        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Redirect to a success page.
            print('redirecting home')
            return redirect("/")

        else:
            test = User.objects.filter(username=username)
            if len(test)==0:
                messages.warning(request,'User not found')
            else:
                messages.error(request,'Check your Password')

            # print('user Not found')
            return render(request, "accounts/login.html", {"msg": msg, })
            # Return an 'invalid login' error message.


    return render(request, "accounts/login.html", {})

    # return render(request, "accounts/login.html", {})



def register_user(request):
    msg = None
    success = False

    if request.method == "POST":
        print('registration_page')
        form = UserCreationForm(request.POST)

        if form.is_valid():

            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)

            msg = 'User created.'

            success = True

            return redirect("home")

        else:
            print(3)
            messages.warning(request, form.error_messages)

            form = UserCreationForm()
            msg = 'Form is not valid'
    else:
        print(4)
        # messages.warning(request, 'just a message')

        form = UserCreationForm()


    return render(request, "accounts/register.html", {"form": form, "msg": msg, "success": success})

def log_out(request):
    logout(request)
    # return render(request, "accounts/login.html", {}

    return redirect("/")
