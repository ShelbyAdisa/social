from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Profile, Post, Comment, Notification
from .serializers import ProfileSerializer, PostSerializer, CommentSerializer, NotificationSerializer
from .forms import UserRegistrationForm, PostForm, CommentForm, ProfileUpdateForm


def home(request):
    if request.user.is_authenticated:
        # Get posts from followed users
        following_users = request.user.profile.user.following.all()
        posts = Post.objects.filter(
            Q(author__in=[profile.user for profile in following_users]) | 
            Q(author=request.user)
        ).distinct()
        
        paginator = Paginator(posts, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        return render(request, 'home.html', {'page_obj': page_obj})
    else:
        return render(request, 'landing.html')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user)
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, '/register.html', {'form': form})

@login_required
def profile(request, username):
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)
    posts = Post.objects.filter(author=user)
    
    context = {
        'profile': profile,
        'posts': posts,
        'is_following': request.user.profile.user in profile.followers.all() if request.user != user else False
    }
    return render(request, 'profile.html', context)

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('home')
    else:
        form = PostForm()
    return render(request, 'create_post.html', {'form': form})

@login_required
def search_users(request):
    query = request.GET.get('q')
    users = []
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id)
    
    return render(request, 'search.html', {'users': users, 'query': query})
# Profile API Views
class ProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        user_id = self.kwargs['user_id']
        user = get_object_or_404(User, id=user_id)
        profile, created = Profile.objects.get_or_create(user=user)
        return profile

# Post API Views
class PostListCreateView(generics.ListCreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Post.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Post.objects.all()
    
    def perform_update(self, serializer):
        if serializer.instance.author != self.request.user:
            raise PermissionError("You can only edit your own posts.")
        serializer.save()
    
    def perform_destroy(self, instance):
        if instance.author != self.request.user:
            raise PermissionError("You can only delete your own posts.")
        instance.delete()

# Comment API Views
class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        post_id = self.kwargs['post_id']
        return Comment.objects.filter(post_id=post_id)
    
    def perform_create(self, serializer):
        post_id = self.kwargs['post_id']
        post = get_object_or_404(Post, id=post_id)
        comment = serializer.save(author=self.request.user, post=post)
        
        # Create notification
        if post.author != self.request.user:
            Notification.objects.create(
                recipient=post.author,
                sender=self.request.user,
                notification_type='comment',
                post=post,
                comment=comment
            )

class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Comment.objects.all()
    
    def perform_update(self, serializer):
        if serializer.instance.author != self.request.user:
            raise PermissionError("You can only edit your own comments.")
        serializer.save()
    
    def perform_destroy(self, instance):
        if instance.author != self.request.user:
            raise PermissionError("You can only delete your own comments.")
        instance.delete()

# Like/Unlike API Views
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if request.method == 'POST':
        if request.user not in post.likes.all():
            post.likes.add(request.user)
            # Create notification
            if post.author != request.user:
                Notification.objects.create(
                    recipient=post.author,
                    sender=request.user,
                    notification_type='like_post',
                    post=post
                )
            return Response({'message': 'Post liked successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Post already liked'}, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        if request.user in post.likes.all():
            post.likes.remove(request.user)
            return Response({'message': 'Post unliked successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Post not liked'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    
    if request.method == 'POST':
        if request.user not in comment.likes.all():
            comment.likes.add(request.user)
            # Create notification
            if comment.author != request.user:
                Notification.objects.create(
                    recipient=comment.author,
                    sender=request.user,
                    notification_type='like_comment',
                    comment=comment
                )
            return Response({'message': 'Comment liked successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Comment already liked'}, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        if request.user in comment.likes.all():
            comment.likes.remove(request.user)
            return Response({'message': 'Comment unliked successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Comment not liked'}, status=status.HTTP_400_BAD_REQUEST)

# Follow/Unfollow API Views
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def follow_user(request, user_id):
    user_to_follow = get_object_or_404(User, id=user_id)
    
    if user_to_follow == request.user:
        return Response({'message': 'You cannot follow yourself'}, status=status.HTTP_400_BAD_REQUEST)
    
    profile_to_follow, created = Profile.objects.get_or_create(user=user_to_follow)
    
    if request.method == 'POST':
        if request.user not in profile_to_follow.followers.all():
            profile_to_follow.followers.add(request.user)
            # Create notification
            Notification.objects.create(
                recipient=user_to_follow,
                sender=request.user,
                notification_type='follow'
            )
            return Response({'message': 'User followed successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Already following this user'}, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        if request.user in profile_to_follow.followers.all():
            profile_to_follow.followers.remove(request.user)
            return Response({'message': 'User unfollowed successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Not following this user'}, status=status.HTTP_400_BAD_REQUEST)

# Search API Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_users_api(request):
    query = request.GET.get('query', '')
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id)[:10]
        
        results = []
        for user in users:
            profile, created = Profile.objects.get_or_create(user=user)
            results.append({
                'id': user.id,
                'username': user.username,
                'full_name': f"{user.first_name} {user.last_name}".strip(),
                'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
                'followers_count': profile.followers_count
            })
        
        return Response({'results': results}, status=status.HTTP_200_OK)
    
    return Response({'results': []}, status=status.HTTP_200_OK)