from django.urls import reverse
from django.utils.text import slugify
from django.db import models
# Import HTMLField from tinymce.models for content
from tinymce.models import HTMLField


class Blog(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    # Changed back to HTMLField to use TinyMCE for the content editor
    content = HTMLField()
    author = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # This ImageField is for a separate main blog image
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)

    def save(self, *args, **kwargs):
        # Automatically generate slug from title if it's not set
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        # Returns the URL for a specific blog post
        return reverse('blog_details', args=[self.slug])

    def __str__(self):
        # String representation of the Blog object
        return self.title