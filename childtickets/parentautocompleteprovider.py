import re

from trac.core import *
from trac.web.api import IRequestHandler

class AutocompleteParentProvider(Component):

    implements(IRequestHandler)

    min_length = 0

    ### methods for IRequestHandler

    def match_request(self, req):
        """Return whether the handler wants to process the given request."""
        return req.path_info.rstrip('/') == '/ac-parent'

    def process_request(self, req):
        """Process the request. Return a (template_name, data, content_type) tuple, 
        where `data` is a dictionary of substitutions for the template.

        "text/html" is assumed if `content_type` is `None`.

        Note that if template processing should not occur, this method can
        simply send the response itself and not return anything.
        """

        query = req.args.get('q', '').lower()
        limit = req.args.get('limit', '20')
        if len(query) < self.min_length:
            req.send(''.encode('utf-8'), 'text/plain')
            return

        milestones = []
        sql = '''SELECT id, summary
                 FROM ticket 
                 WHERE type = 'milestone' 
                   AND status != 'closed'
                   AND summary LIKE %s
                 ORDER BY summary
                 LIMIT %s'''
        args = ['%%%s%%' % query, limit]
        for ticket_id, ticket_summary in self.env.db_query(sql, args):
            milestones.append("%s|%s" % (ticket_id, ticket_summary))

        req.send('\n'.join(milestones).encode('utf-8'), 'text/plain')


