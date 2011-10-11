from pkg_resources import resource_filename

from trac.core import *

from trac.web.api import IRequestFilter
from trac.web.chrome import add_script, add_script_data
from trac.web.chrome import add_stylesheet
from trac.web.chrome import ITemplateProvider 

class AutocompleteParentExtendPage(Component):

    implements(IRequestFilter, ITemplateProvider)

    prefix = "ct" # prefix for htdocs -- /chrome/prefix/...    

    ### methods for ITemplateProvider

    def get_htdocs_dirs(self):
        return [(self.prefix, resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        return []

    ### methods for IRequestFilter

    def post_process_request(self, req, template, data, content_type):
        """Do any post-processing the request might need; typically adding
        values to the template `data` dictionary, or changing template or
        mime type.
        
        `data` may be update in place.

        Always returns a tuple of (template, data, content_type), even if
        unchanged.

        Note that `template`, `data`, `content_type` will be `None` if:
         - called when processing an error page
         - the default request handler did not return any result

        (Since 0.11)
        """
        if template == 'ticket.html':
            add_stylesheet(req, '%s/css/autocomplete.css' % self.prefix)
            add_script(req, '%s/js/autocomplete.js' % self.prefix)
            if req.path_info.rstrip() == '/newticket':
                add_script_data(req, {'PARENT_AC_PATH': 'ac-parent'})
            else:
                add_script_data(req, {'PARENT_AC_PATH': '../ac-parent'})
            add_script(req, '%s/js/autocomplete_parent.js' % self.prefix)
        return (template, data, content_type)

    def pre_process_request(self, req, handler):
        """Called after initial handler selection, and can be used to change
        the selected handler or redirect request.
        
        Always returns the request handler, even if unchanged.
        """
        return handler
