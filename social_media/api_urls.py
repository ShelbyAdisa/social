from django.urls import path
from . import views

urlpatterns = [
    # Profile endpoints
    path('profiles/<int:user_id>/', views.ProfileDetailView.as_view(), name='profile-detail'),
    
    # Post endpoints
    path('posts/', views.PostListCreateView.as_view(), name='post-list-create'),
    path('posts/<int:pk>/', views.PostDetailView.as_view(), name='post-detail'),
    
    # Comment endpoints
    path('posts/<int:post_id>/comments/', views.CommentListCreateView.as_view(), name='comment-list-create'),
    path('comments/<int:pk>/', views.CommentDetailView.as_view(), name='comment-detail'),
    
    # Like endpoints
    path('posts/<int:post_id>/like/', views.like_post, name='like-post'),
    path('comments/<int:comment_id>/like/', views.like_comment, name='like-comment'),
    
    # Follow endpoints
    path('users/<int:user_id>/follow/', views.follow_user, name='follow-user'),
    
    # Search endpoints
    path('search/users/', views.search_users_api, name='search-users'),
]