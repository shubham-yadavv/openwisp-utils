from django.contrib.admin import ModelAdmin, StackedInline
from django.core.exceptions import FieldError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class TimeReadonlyAdminMixin(object):
    """
    mixin that automatically flags
    `created` and `modified` as readonly
    """

    def __init__(self, *args, **kwargs):
        self.readonly_fields += ('created', 'modified')
        super().__init__(*args, **kwargs)


class ReadOnlyAdmin(ModelAdmin):
    """
    Disables all editing capabilities
    """

    exclude = tuple()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        exclude = self.exclude
        self.readonly_fields = [
            f.name for f in self.model._meta.fields if f.name not in exclude
        ]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:  # pragma: no cover
            del actions['delete_selected']
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):  # pragma: nocover
        pass

    def delete_model(self, request, obj):  # pragma: nocover
        pass

    def save_related(self, request, form, formsets, change):  # pragma: nocover
        pass

    def change_view(self, request, object_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save_and_continue'] = False
        extra_context['show_save'] = False
        return super().change_view(request, object_id, extra_context=extra_context)


class AlwaysHasChangedMixin(object):
    def has_changed(self):
        """
        This django-admin trick ensures the inline item
        is saved even if default values are unchanged
        (without this trick new objects won't be
        created unless users change the default values)
        """
        if self.instance._state.adding:
            return True
        return super().has_changed()


class CopyableFieldError(FieldError):
    pass


class CopyableFieldsAdmin(ModelAdmin):
    """
    An admin class that allows to set admin
    fields to be read-only and makes it easy
    to copy the fields contents.
    Useful for auto-generated fields such as
    UUIDs, secret keys, tokens, etc
    """

    copyable_fields = ()
    change_form_template = 'admin/change_form.html'

    def _check_copyable_subset_fields(self, copyable_fields, fields):
        if not set(copyable_fields).issubset(fields):
            class_name = self.__class__.__name__
            raise CopyableFieldError(
                (
                    f'{copyable_fields} not in {class_name}.fields {fields}, '
                    f'Check copyable_fields attribute of class {class_name}.'
                )
            )

    def get_fields(self, request, obj=None):
        fields = super(ModelAdmin, self).get_fields(request, obj)
        self._check_copyable_subset_fields(self.copyable_fields, fields)
        # We should exclude `copyable_fields` fields
        # when the object doesn't exist for example,
        # in the case of `add_view` because `copyable_fields`
        # can't be edited and are auto generated by the system
        if not obj:
            return tuple(set(fields).difference(self.copyable_fields))
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super(ModelAdmin, self).get_readonly_fields(request, obj)
        if not obj:
            return readonly_fields
        # Make sure `copyable_fields` is included in `read_only` fields
        return tuple([*readonly_fields, *self.copyable_fields])

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['copyable_fields'] = []
        return super().add_view(
            request,
            form_url,
            extra_context=extra_context,
        )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['copyable_fields'] = list(self.copyable_fields)
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

    class Media:
        js = ('admin/js/jquery.init.js', 'openwisp-utils/js/copyable.js')


class UUIDAdmin(CopyableFieldsAdmin):
    """
    This class is a subclass of `CopyableFieldsAdmin`
    which sets `uuid` as the only copyable field
    This class is kept for backward compatibility
    and convenience, since different models of various
    OpenWISP modules show `uuid` as the only copyable field
    """

    copyable_fields = ('uuid',)

    def uuid(self, obj):
        return obj.pk

    uuid.short_description = _('UUID')


class ReceiveUrlAdmin(ModelAdmin):
    """
    Return a receive_url field whose value is that of
    a view_name concatenated with the obj id and/or
    with the key of the obj
    """

    receive_url_querystring_arg = 'key'
    receive_url_object_arg = 'pk'
    receive_url_name = None
    receive_url_urlconf = None
    receive_url_baseurl = None

    def add_view(self, request, *args, **kwargs):
        self.request = request
        return super().add_view(request, *args, **kwargs)

    def change_view(self, request, *args, **kwargs):
        self.request = request
        return super().change_view(request, *args, **kwargs)

    def receive_url(self, obj):
        """
        :param obj: Object for which the url is generated
        """
        if self.receive_url_name is None:
            raise ValueError('receive_url_name is not set up')
        reverse_kwargs = {}
        if self.receive_url_object_arg:
            reverse_kwargs = {
                self.receive_url_object_arg: getattr(obj, self.receive_url_object_arg)
            }
        receive_path = reverse(
            self.receive_url_name,
            urlconf=self.receive_url_urlconf,
            kwargs=reverse_kwargs,
        )
        baseurl = self.receive_url_baseurl
        if not baseurl:
            baseurl = '{0}://{1}'.format(self.request.scheme, self.request.get_host())
        if self.receive_url_querystring_arg:
            url = '{0}{1}?{2}={3}'.format(
                baseurl,
                receive_path,
                self.receive_url_querystring_arg,
                getattr(obj, self.receive_url_querystring_arg),
            )
        return url

    class Media:
        js = ('admin/js/jquery.init.js', 'openwisp-utils/js/receive_url.js')

    receive_url.short_description = _('URL')


class HelpTextStackedInline(StackedInline):
    help_text = None
    template = 'admin/edit_inline/help_text_stacked.html'

    class Media:
        css = {'all': ['admin/css/help-text-stacked.css']}

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.help_text = self.help_text
        return formset
