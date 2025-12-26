"""
Vulnerable Django Views - Test Fixture

Django-specific vulnerability patterns for taint analysis testing.
"""

from django.shortcuts import render
from django.http import HttpResponse
from django.db import connection
from django.utils.safestring import mark_safe
import os


# ============================================================================
# SQL Injection in Django
# ============================================================================

def vulnerable_user_search(request):
    """
    SQL injection using raw queries.
    
    Taint flow:
    Source: request.GET['query']
    Sink: cursor.execute()
    """
    search = request.GET.get('query', '')  # SOURCE
    
    with connection.cursor() as cursor:
        # VULNERABLE: String formatting in raw SQL
        sql = f"SELECT * FROM users WHERE name LIKE '%{search}%'"
        cursor.execute(sql)  # SINK
        results = cursor.fetchall()
        
    return HttpResponse(str(results))


def vulnerable_raw_query(request):
    """
    Using Django's .raw() with user input.
    
    Taint flow:
    Source: request.POST['user_id']
    Sink: Model.objects.raw()
    """
    user_id = request.POST.get('user_id')  # SOURCE
    
    # VULNERABLE: .raw() with string formatting
    from myapp.models import User
    users = User.objects.raw(
        f"SELECT * FROM users WHERE id = {user_id}"
    )  # SINK
    
    return HttpResponse(list(users))


# ============================================================================
# XSS in Django Templates
# ============================================================================

def vulnerable_template_xss(request):
    """
    XSS via mark_safe() on user input.
    
    Taint flow:
    Source: request.GET['html']
    Sink: mark_safe()
    """
    user_html = request.GET.get('html', '')  # SOURCE
    
    # VULNERABLE: mark_safe bypasses escaping
    safe_html = mark_safe(user_html)  # SINK
    
    return render(request, 'display.html', {'content': safe_html})


def vulnerable_direct_html(request):
    """
    XSS via direct HTML response.
    
    Taint flow:
    Source: request.POST['comment']
    Sink: HttpResponse with HTML
    """
    comment = request.POST.get('comment', '')  # SOURCE
    
    # VULNERABLE: Direct HTML rendering
    html = f"<div class='user-comment'>{comment}</div>"
    return HttpResponse(html)  # SINK


# ============================================================================
# Command Injection in Django
# ============================================================================

def vulnerable_file_converter(request):
    """
    Command injection via subprocess.
    
    Taint flow:
    Source: request.FILES['file'].name
    Sink: os.system()
    """
    uploaded_file = request.FILES.get('file')
    filename = uploaded_file.name  # SOURCE
    
    # VULNERABLE: os.system with user-controlled filename
    os.system(f"convert {filename} output.pdf")  # SINK
    
    return HttpResponse("Converted")


# ============================================================================
# SAFE Examples
# ============================================================================

def safe_user_search(request):
    """
    SAFE: Using Django ORM.
    """
    search = request.GET.get('query', '')
    
    from myapp.models import User
    # SAFE: ORM handles parameterization
    users = User.objects.filter(name__icontains=search)
    
    return HttpResponse(str(list(users)))


def safe_template_render(request):
    """
    SAFE: Django template auto-escaping.
    """
    user_input = request.GET.get('data', '')
    
    # SAFE: Django templates escape by default
    return render(request, 'safe.html', {'data': user_input})
