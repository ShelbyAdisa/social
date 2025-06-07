# social_media/signals.py
from django.db.models.signals import post_save, pre_delete, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.cache import cache
from .models import Profile, Post, Comment, Notification
import os


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a user profile when a new user is created
    """
    if created:
        Profile.objects.create(user=instance)
        print(f"Profile created for user: {instance.username}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save user profile when user is saved
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Post)
def post_created_notification(sender, instance, created, **kwargs):
    """
    Create notifications for followers when a new post is created
    """
    if created:
        # Get all followers of the post author
        followers = instance.author.profile.followers.all()
        
        # Create notifications for each follower
        notifications_to_create = []
        for follower in followers:
            if follower != instance.author:  # Don't notify self
                notifications_to_create.append(
                    Notification(
                        recipient=follower,
                        sender=instance.author,
                        notification_type='follow',  # You might want to add 'new_post' type
                        post=instance
                    )
                )
        
        if notifications_to_create:
            Notification.objects.bulk_create(notifications_to_create)


@receiver(m2m_changed, sender=Post.likes.through)
def post_like_notification(sender, instance, action, pk_set, **kwargs):
    """
    Create notification when someone likes a post
    """
    if action == 'post_add':
        for user_id in pk_set:
            liker = User.objects.get(pk=user_id)
            if liker != instance.author:  # Don't notify if user likes their own post
                # Check if notification already exists to avoid duplicates
                if not Notification.objects.filter(
                    recipient=instance.author,
                    sender=liker,
                    notification_type='like_post',
                    post=instance
                ).exists():
                    Notification.objects.create(
                        recipient=instance.author,
                        sender=liker,
                        notification_type='like_post',
                        post=instance
                    )


@receiver(m2m_changed, sender=Comment.likes.through)
def comment_like_notification(sender, instance, action, pk_set, **kwargs):
    """
    Create notification when someone likes a comment
    """
    if action == 'post_add':
        for user_id in pk_set:
            liker = User.objects.get(pk=user_id)
            if liker != instance.author:  # Don't notify if user likes their own comment
                # Check if notification already exists to avoid duplicates
                if not Notification.objects.filter(
                    recipient=instance.author,
                    sender=liker,
                    notification_type='like_comment',
                    comment=instance
                ).exists():
                    Notification.objects.create(
                        recipient=instance.author,
                        sender=liker,
                        notification_type='like_comment',
                        comment=instance
                    )


@receiver(post_save, sender=Comment)
def comment_created_notification(sender, instance, created, **kwargs):
    """
    Create notification when someone comments on a post
    """
    if created:
        if instance.author != instance.post.author:  # Don't notify if user comments on their own post
            # Check if notification already exists to avoid duplicates
            if not Notification.objects.filter(
                recipient=instance.post.author,
                sender=instance.author,
                notification_type='comment',
                post=instance.post,
                comment=instance
            ).exists():
                Notification.objects.create(
                    recipient=instance.post.author,
                    sender=instance.author,
                    notification_type='comment',
                    post=instance.post,
                    comment=instance
                )


@receiver(m2m_changed, sender=Profile.followers.through)
def follow_notification(sender, instance, action, pk_set, **kwargs):
    """
    Create notification when someone follows a user
    """
    if action == 'post_add':
        for follower_id in pk_set:
            follower = User.objects.get(pk=follower_id)
            if follower != instance.user:  # Don't notify if user follows themselves
                # Check if notification already exists to avoid duplicates
                if not Notification.objects.filter(
                    recipient=instance.user,
                    sender=follower,
                    notification_type='follow'
                ).exists():
                    Notification.objects.create(
                        recipient=instance.user,
                        sender=follower,
                        notification_type='follow'
                    )


@receiver(post_delete, sender=Post)
def delete_post_image(sender, instance, **kwargs):
    """
    Delete associated image file when a post is deleted
    """
    if instance.image:
        if os.path.isfile(instance.image.path):
            try:
                os.remove(instance.image.path)
                print(f"Deleted post image: {instance.image.path}")
            except Exception as e:
                print(f"Error deleting post image: {e}")


@receiver(pre_delete, sender=Profile)
def delete_profile_picture(sender, instance, **kwargs):
    """
    Delete profile picture when profile is deleted (except default)
    """
    if instance.profile_picture and 'default.jpg' not in instance.profile_picture.name:
        if os.path.isfile(instance.profile_picture.path):
            try:
                os.remove(instance.profile_picture.path)
                print(f"Deleted profile picture: {instance.profile_picture.path}")
            except Exception as e:
                print(f"Error deleting profile picture: {e}")


@receiver(post_save, sender=Profile)
def delete_old_profile_picture(sender, instance, created, **kwargs):
    """
    Delete old profile picture when a new one is uploaded (not when created)
    """
    if not created:  # Only run for updates, not creation
        try:
            # Get the old instance from database
            old_profile = Profile.objects.get(pk=instance.pk)
            if old_profile.profile_picture != instance.profile_picture:
                if old_profile.profile_picture and 'default.jpg' not in old_profile.profile_picture.name:
                    if os.path.isfile(old_profile.profile_picture.path):
                        os.remove(old_profile.profile_picture.path)
                        print(f"Deleted old profile picture: {old_profile.profile_picture.path}")
        except Profile.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error deleting old profile picture: {e}")


@receiver(post_save, sender=Post)
def clear_user_posts_cache(sender, instance, **kwargs):
    """
    Clear cached data when posts are created or updated
    """
    # Clear user's posts cache
    cache.delete(f'user_posts_{instance.author.id}')
    cache.delete(f'user_posts_count_{instance.author.id}')
    
    # Clear home timeline cache for followers
    followers = instance.author.profile.followers.all()
    for follower in followers:
        cache.delete(f'home_timeline_{follower.id}')


@receiver(post_delete, sender=Post)
def clear_user_posts_cache_on_delete(sender, instance, **kwargs):
    """
    Clear cached data when posts are deleted
    """
    cache.delete(f'user_posts_{instance.author.id}')
    cache.delete(f'user_posts_count_{instance.author.id}')
    
    followers = instance.author.profile.followers.all()
    for follower in followers:
        cache.delete(f'home_timeline_{follower.id}')


@receiver(post_save, sender=Comment)
def clear_post_comments_cache(sender, instance, **kwargs):
    """
    Clear post comments cache when a new comment is added
    """
    cache.delete(f'post_comments_{instance.post.id}')
    cache.delete(f'post_comments_count_{instance.post.id}')


@receiver(post_delete, sender=Comment)
def clear_post_comments_cache_on_delete(sender, instance, **kwargs):
    """
    Clear post comments cache when a comment is deleted
    """
    cache.delete(f'post_comments_{instance.post.id}')
    cache.delete(f'post_comments_count_{instance.post.id}')


@receiver(post_save, sender=Notification)
def clear_notifications_cache(sender, instance, **kwargs):
    """
    Clear user notifications cache when a new notification is created
    """
    cache.delete(f'user_notifications_{instance.recipient.id}')
    cache.delete(f'unread_notifications_count_{instance.recipient.id}')


@receiver(post_save, sender=Notification)
def mark_notification_cache_update(sender, instance, created, **kwargs):
    """
    Update notification cache when notification is read/unread
    """
    if not created:  # Only for updates, not creation
        cache.delete(f'user_notifications_{instance.recipient.id}')
        cache.delete(f'unread_notifications_count_{instance.recipient.id}')


# Clean up notifications when related objects are deleted
@receiver(post_delete, sender=Post)
def delete_post_notifications(sender, instance, **kwargs):
    """
    Delete all notifications related to a post when the post is deleted
    """
    Notification.objects.filter(post=instance).delete()


@receiver(post_delete, sender=Comment)
def delete_comment_notifications(sender, instance, **kwargs):
    """
    Delete all notifications related to a comment when the comment is deleted
    """
    Notification.objects.filter(comment=instance).delete()


@receiver(pre_delete, sender=User)
def cleanup_user_data(sender, instance, **kwargs):
    """
    Clean up user-related data before user deletion
    """
    # Delete notifications sent by this user
    Notification.objects.filter(sender=instance).delete()
    
    # Delete notifications received by this user
    Notification.objects.filter(recipient=instance).delete()
    
    # Clear all related cache
    cache.delete(f'user_posts_{instance.id}')
    cache.delete(f'user_posts_count_{instance.id}')
    cache.delete(f'home_timeline_{instance.id}')
    cache.delete(f'user_notifications_{instance.id}')
    cache.delete(f'unread_notifications_count_{instance.id}')


print("Social media signals loaded successfully!")