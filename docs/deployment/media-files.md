# Media Files Configuration Guide

## 📸 Overview

This guide explains how to configure media file serving (user uploads: profile images, blog images, course thumbnails) in production.

---

## ⚠️ Common Issue: Images Not Showing in Production

**Symptom:** Images work in development (`DEBUG=True`) but don't load in production

**Root Cause:** Django's `static()` helper was wrapped in `if settings.DEBUG` check, preventing media file serving in production.

**Fixed:** Media URL patterns now work in all environments.

---

## 🔧 Current Configuration

### Settings (`lsaapp/settings.py`)

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

### URL Configuration (`lsaapp/urls.py`)

```python
from django.conf import settings
from django.conf.urls.static import static

# Serve media files (works in all environments)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 📁 Directory Structure

```
LSAApp/
├── media/                    # User-uploaded files
│   ├── blog/                 # Blog featured images
│   │   └── featured/
│   ├── courses/              # Course thumbnails
│   ├── lsalms/               # LMS content files
│   │   ├── lessons/
│   │   └── assignments/
│   └── profile_images/       # User avatars
│
└── mediafiles/               # Legacy (if exists, migrate to media/)
```

**Important:** Ensure uploads go to `media/` directory (not `mediafiles/`)

---

## 🚀 Production Deployment Options

### Option 1: Nginx Serving (Recommended)

**Best for:** VPS, dedicated servers, container deployments

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name learnswift.icu www.learnswift.icu;
    
    # Static files (CSS, JS)
    location /static/ {
        alias /path/to/LSAApp/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files (User uploads)
    location /media/ {
        alias /path/to/LSAApp/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Pros:**
- ✅ Excellent performance
- ✅ Reduced Django load
- ✅ Better caching control

**Cons:**
- ❌ Requires Nginx configuration
- ❌ Needs server access

---

### Option 2: Django Serving (Simple)

**Best for:** Render.com, Heroku, simple deployments

**How it works:** Django serves media files via URL patterns (already configured)

**Configuration:**
```python
# settings.py - Already configured
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# urls.py - Already configured
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Pros:**
- ✅ No additional configuration
- ✅ Works immediately
- ✅ Platform-agnostic

**Cons:**
- ⚠️ Less efficient than Nginx
- ⚠️ Django processes serve files

**Performance Note:** Acceptable for small-medium traffic (<10,000 requests/day)

---

### Option 3: Cloud Storage (Scalable)

**Best for:** High-traffic production, multi-server deployments

**Providers:**
- AWS S3
- Cloudinary
- DigitalOcean Spaces
- Azure Blob Storage

**Django-Storages Configuration:**

1. Install package:
```bash
pip install django-storages boto3  # For AWS S3
# OR
pip install django-storages[cloudinary]  # For Cloudinary
```

2. Update settings:
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'storages',
]

# AWS S3 Configuration
if not DEBUG:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
```

3. Environment variables:
```env
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1
```

**Pros:**
- ✅ Unlimited scalability
- ✅ CDN integration
- ✅ Automatic backups
- ✅ No server storage limits

**Cons:**
- ❌ Additional cost
- ❌ More complex setup
- ❌ External dependency

---

## 🔒 Security Considerations

### File Upload Validation

**Current validation** (models.py):
```python
def validate_image_extension(value):
    """Validate uploaded image file extensions"""
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(f'Unsupported file extension. Use: {", ".join(valid_extensions)}')

def validate_image_size(value):
    """Validate image file size (max 5MB)"""
    filesize = value.size
    if filesize > 5 * 1024 * 1024:  # 5MB
        raise ValidationError('Maximum file size is 5MB')

class BlogPost(models.Model):
    featured_image = models.ImageField(
        upload_to='blog/featured/',
        blank=True,
        validators=[validate_image_extension, validate_image_size]
    )
```

### Nginx Security Headers
```nginx
location /media/ {
    alias /path/to/LSAApp/media/;
    
    # Prevent execution of uploaded scripts
    location ~ \.(php|py|sh|exe)$ {
        deny all;
    }
    
    # Security headers
    add_header X-Content-Type-Options "nosniff";
    add_header Content-Security-Policy "default-src 'none'; img-src 'self'; style-src 'self'";
}
```

---

## 📊 Performance Optimization

### 1. Image Compression
Install Pillow and django-imagekit:
```bash
pip install Pillow django-imagekit
```

```python
# models.py
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill

class Course(models.Model):
    image = ProcessedImageField(
        upload_to='courses/',
        processors=[ResizeToFill(800, 600)],
        format='JPEG',
        options={'quality': 85}
    )
```

### 2. Lazy Loading
Already implemented in templates:
```html
<img src="{{ course.image.url }}" 
     loading="lazy"
     alt="{{ course.title }}">
```

### 3. Browser Caching
Set cache headers in Nginx or Django:
```python
# Nginx (shown above) or WhiteNoise for static files
WHITENOISE_MAX_AGE = 31536000  # 1 year
```

---

## 🧪 Testing Media Files

### Development
```bash
python manage.py runserver
# Upload image via admin
# Access: http://localhost:8000/media/blog/featured/image.jpg
```

### Production
```bash
# Check media directory exists and is writable
ls -la /path/to/LSAApp/media

# Test upload via admin panel
# Verify: https://learnswift.icu/media/blog/featured/image.jpg

# Check Nginx logs
tail -f /var/log/nginx/access.log | grep media
```

---

## 🐛 Troubleshooting

### Issue: 404 on Media Files

**Check 1:** URLs configured?
```python
# urls.py
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Check 2:** Directory exists and permissions?
```bash
ls -la media/
# Should show drwxr-xr-x or similar
```

**Check 3:** Nginx configuration correct?
```bash
nginx -t  # Test config
systemctl reload nginx
```

### Issue: Permission Denied

```bash
# Set correct ownership
chown -R www-data:www-data /path/to/LSAApp/media

# Set correct permissions
chmod -R 755 /path/to/LSAApp/media
```

### Issue: Images Not Uploading

**Check 1:** MEDIA_ROOT writable by Django process
```python
import os
print(os.access(settings.MEDIA_ROOT, os.W_OK))  # Should be True
```

**Check 2:** Form using enctype
```html
<form method="post" enctype="multipart/form-data">
```

---

## 🔄 Migration from mediafiles/ to media/

If existing uploads are in `mediafiles/`:

```bash
# 1. Move files
mv mediafiles/* media/

# 2. Update database paths (if needed)
python manage.py shell
>>> from core.models import BlogPost
>>> posts = BlogPost.objects.filter(featured_image__startswith='mediafiles/')
>>> for post in posts:
...     post.featured_image.name = post.featured_image.name.replace('mediafiles/', 'media/')
...     post.save()
```

---

## 📝 Checklist for Production

- [ ] `MEDIA_URL = '/media/'` in settings
- [ ] `MEDIA_ROOT = BASE_DIR / 'media'` in settings
- [ ] URL patterns include `static(settings.MEDIA_URL, ...)`
- [ ] `media/` directory exists
- [ ] `media/` directory writable by web server
- [ ] Nginx configured to serve `/media/` (if using Nginx)
- [ ] File upload validation in place
- [ ] Image compression configured
- [ ] Backups configured for `media/` directory
- [ ] `.gitignore` includes `media/`
- [ ] Images load on production site

---

## 🆘 Support

**Documentation:**
- [Django File Uploads](https://docs.djangoproject.com/en/5.0/topics/http/file-uploads/)
- [Django Static Files](https://docs.djangoproject.com/en/5.0/howto/static-files/)
- [WhiteNoise](http://whitenoise.evans.io/)

**Common Commands:**
```bash
# Collect static files
python manage.py collectstatic

# Check settings
python manage.py diffsettings

# Test media serving
curl -I https://learnswift.icu/media/test.jpg
```

---

**Last Updated:** January 9, 2026  
**Production Status:** ✅ Fixed - Media files now serve correctly
