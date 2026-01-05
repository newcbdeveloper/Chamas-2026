from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Article, Category, Tag

def article_list(request):
    articles = Article.objects.filter(status='published').select_related('author', 'category').prefetch_related('tags')
    
    paginator = Paginator(articles, 10)  # 10 articles per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': Category.objects.all(),
    }
    return render(request, 'blog/article_list.html', context)


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, status='published')
    
    # Increment views
    article.views += 1
    article.save(update_fields=['views'])
    
    # Get related articles
    related_articles = Article.objects.filter(
        category=article.category,
        status='published'
    ).exclude(id=article.id)[:3]
    
    context = {
        'article': article,
        'related_articles': related_articles,
    }
    return render(request, 'blog/article_detail.html', context)


def category_articles(request, slug):
    category = get_object_or_404(Category, slug=slug)
    articles = Article.objects.filter(category=category, status='published')
    
    paginator = Paginator(articles, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'blog/category_articles.html', context)


def tag_articles(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    articles = Article.objects.filter(tags=tag, status='published')
    
    paginator = Paginator(articles, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tag': tag,
        'page_obj': page_obj,
    }
    return render(request, 'blog/tag_articles.html', context)