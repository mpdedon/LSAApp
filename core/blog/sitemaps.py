# blog/sitemaps.py
from django.contrib.sitemaps import Sitemap
from core.models import Post, Category 

class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9 # Higher for important content

    def items(self):
        return Post.published_objects.all()

    def lastmod(self, obj):
        return obj.updated_at # Or published_date

class CategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Category.objects.all()

    # lastmod is optional for categories if they don't have a meaningful update date