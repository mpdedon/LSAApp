# blog/views.py
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q 
from core.models import Post, Category, Tag
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class PostListView(ListView):
    model = Post
    template_name = 'blog/post_list.html' 
    context_object_name = 'posts'
    paginate_by = 10

    def get_queryset(self):
        queryset = Post.published_objects.all().select_related('author__student', 'author__teacher', 'author__guardian')

        category_slug = self.kwargs.get('category_slug')
        tag_slug = self.kwargs.get('tag_slug')
        author_username = self.kwargs.get('username')

        if category_slug:
            category = get_object_or_404(Category, slug=category_slug)
            queryset = queryset.filter(categories=category)
            self.category = category 
        elif tag_slug:
            tag = get_object_or_404(Tag, slug=tag_slug)
            queryset = queryset.filter(tags=tag)
            self.tag = tag # For context
        elif author_username:
            author = get_object_or_404(CustomUser, username=author_username)
            queryset = queryset.filter(author=author)
            self.author_obj = author 

        # Search functionality (optional)
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(content__icontains=query)
            ).distinct()
            self.search_query = query

        return queryset.prefetch_related('categories', 'tags') 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['tags'] = Tag.objects.all() # Or most popular tags
        if hasattr(self, 'category'):
            context['archive_title'] = f"Posts in Category: {self.category.name}"
        elif hasattr(self, 'tag'):
            context['archive_title'] = f"Posts Tagged: {self.tag.name}"
        elif hasattr(self, 'author_obj'):
            context['archive_title'] = f"Posts by: {self.author_obj.get_full_name() or self.author_obj.username}"
        elif hasattr(self, 'search_query'):
             context['archive_title'] = f"Search Results for: \"{self.search_query}\""
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'

    def get_queryset(self):
        return Post.published_objects.all().select_related('author') \
                   .prefetch_related('categories', 'tags')

    def get_object(self, queryset=None):
        # Override to increment views count
        obj = super().get_object(queryset=queryset)
        obj.increment_views()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        # Related posts (simple example: same category, exclude current post)
        if post.categories.exists():
            first_category = post.categories.first()
            context['related_posts'] = Post.published_objects.filter(
                categories=first_category
            ).exclude(pk=post.pk).select_related('author').prefetch_related('categories')[:3] # Show 3 related
        else:
            context['related_posts'] = Post.published_objects.exclude(pk=post.pk).order_by('?')[:3] # Random if no category

        context['categories'] = Category.objects.all()
        context['tags'] = Tag.objects.all()
        return context


class BlogSearchView(PostListView): 
    template_name = 'blog/search_results.html'
    # get_queryset handles search via GET['q']