# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django import forms
from django.db import models
from django.contrib import admin
from django.conf import settings
from django.forms.widgets import TextInput
from django.utils import six
from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _

from .fields import CommaSeparatedEmailField
from .models import Attachment, Log, Email, EmailTemplate, STATUS


def get_message_preview(instance):
    return (u'{0}...'.format(instance.message[:25]) if len(instance.message) > 25
            else instance.message)

get_message_preview.short_description = 'Message'


class LogInline(admin.StackedInline):
    model = Log
    extra = 0


class CommaSeparatedEmailWidget(TextInput):

    def __init__(self, *args, **kwargs):
        super(CommaSeparatedEmailWidget, self).__init__(*args, **kwargs)
        self.attrs.update({'class': 'vTextField'})

    def format_value(self, value):
        # If the value is a string wrap it in a list so it does not get sliced.
        if not value:
            return ''
        if isinstance(value, six.string_types):
            value = [value, ]
        return ','.join([item for item in value])


def requeue(modeladmin, request, queryset):
    """An admin action to requeue emails."""
    queryset.update(status=STATUS.queued)


requeue.short_description = 'Requeue selected emails'


class EmailAdmin(admin.ModelAdmin):
    list_display = ('id', 'to_display', 'subject', 'template',
                    'status', 'last_updated')
    search_fields = ['to', 'subject']
    date_hierarchy = 'last_updated'
    inlines = [LogInline]
    list_filter = ['status', 'template__language', 'template__name']
    formfield_overrides = {
        CommaSeparatedEmailField: {'widget': CommaSeparatedEmailWidget}
    }
    actions = [requeue]

    def get_queryset(self, request):
        return super(EmailAdmin, self).get_queryset(request).select_related('template')

    def to_display(self, instance):
        return ', '.join(instance.to)

    to_display.short_description = 'to'
    to_display.admin_order_field = 'to'


class LogAdmin(admin.ModelAdmin):
    list_display = ('date', 'email', 'status', get_message_preview)


class SubjectField(TextInput):
    def __init__(self, *args, **kwargs):
        super(SubjectField, self).__init__(*args, **kwargs)
        self.attrs.update({'style': 'width: 610px;'})


class EmailTemplateAdminForm(forms.ModelForm):

    language = forms.ChoiceField(choices=settings.LANGUAGES, required=False,
                                 help_text=_("Render template in alternative language"),
                                 label=_("Language"))

    class Meta:
        model = EmailTemplate
        fields = ('name', 'description', 'subject',
                  'content', 'html_content', 'language', 'default_template')


class EmailTemplateInline(admin.StackedInline):
    form = EmailTemplateAdminForm
    model = EmailTemplate
    extra = 0
    fields = ('language', 'subject', 'content', 'html_content',)
    formfield_overrides = {
        models.CharField: {'widget': SubjectField}
    }

    def get_max_num(self, request, obj=None, **kwargs):
        return len(settings.LANGUAGES)


class EmailTemplateAdmin(admin.ModelAdmin):
    form = EmailTemplateAdminForm
    list_display = ('name', 'description_shortened', 'subject', 'languages_compact', 'created')
    search_fields = ('name', 'description', 'subject')
    fieldsets = [
        (None, {
            'fields': ('name', 'description'),
        }),
        (_("Default Content"), {
            'fields': ('subject', 'content', 'html_content'),
        }),
    ]
    inlines = (EmailTemplateInline,) if settings.USE_I18N else ()
    formfield_overrides = {
        models.CharField: {'widget': SubjectField}
    }

    def get_queryset(self, request):
        return self.model.objects.filter(default_template__isnull=True)

    def description_shortened(self, instance):
        return Truncator(instance.description.split('\n')[0]).chars(200)
    description_shortened.short_description = _("Description")
    description_shortened.admin_order_field = 'description'

    def languages_compact(self, instance):
        languages = [tt.language for tt in instance.translated_templates.order_by('language')]
        return ', '.join(languages)
    languages_compact.short_description = _("Languages")

    def save_model(self, request, obj, form, change):
        obj.save()

        # if the name got changed, also change the translated templates to match again
        if 'name' in form.changed_data:
            obj.translated_templates.update(name=obj.name)


class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'file', )


admin.site.register(Email, EmailAdmin)
admin.site.register(Log, LogAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(Attachment, AttachmentAdmin)
