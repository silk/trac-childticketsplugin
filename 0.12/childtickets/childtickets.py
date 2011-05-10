# ChildTickets plugin

import re

from trac.core import *
from trac.cache import cached
from trac.ticket.api import ITicketManipulator, ITicketChangeListener
from trac.web.api import ITemplateStreamFilter
from trac.perm import IPermissionRequestor
from trac.ticket.model import Ticket
from trac.resource import ResourceNotFound

from genshi.builder import tag
from genshi.filters import Transformer

class TracchildticketsModule(Component):
    implements(ITicketManipulator, ITemplateStreamFilter, ITicketChangeListener)


    @cached
    def childtickets(self,db):
        # NOTE: Ignore the above 'db' arg that is supplied to '@cached' decorated functions - I think I read somewhere that
        # this is no longer supported. (But I'm keeping it here for compatibility!)
        db = self.env.get_db_cnx() 
        cursor = db.cursor() 
        cursor.execute("SELECT ticket,value FROM ticket_custom WHERE name='parent'")
        x = {}    # { parent -> children } - 1:n
        for child,parent in cursor.fetchall():
            if parent and re.match('#\d+',parent):
                x.setdefault( int(parent.lstrip('#')), [] ).append(child)
        return x


    # ITicketChangeListener methods
    def ticket_changed(self, ticket, comment, author, old_values):
        if 'parent' in old_values:
            del self.childtickets

    def ticket_created(self, ticket):
        del self.childtickets

    def ticket_deleted(self, ticket):
        # NOTE: Is there a way to 'block' a ticket deletion if it still has child tickets?
        del self.childtickets


    # ITicketManipulator methods
    def prepare_ticket(self, req, ticket, fields, actions):
        pass
    
    def validate_ticket(self, req, ticket):

        # Don't allow ticket to be 'resolved' if any child tickets are still open.
        if req.args.get('action') == 'resolve':
            for t in self.childtickets.get(ticket.id,[]):
                if Ticket(self.env,t)['status'] != 'closed':
                    yield 'parent', 'Cannot resolve ticket while child ticket (#%s) is still open.' % t

        # Check if the 'parent' field is being used.
        if ticket.values.get('parent'):

            # Is it of correct 'format'?
            if not re.match('^#\d+',ticket.values.get('parent')):
                yield 'parent', "The parent id must be of the form '#id' where 'id' is a valid ticket id."

            # Strip the '#' to get parent id.
            pid = int(ticket.values.get('parent').lstrip('#'))

            # Check we're not being daft and setting own id as parent.
            if ticket.id and pid == ticket.id:
                yield 'parent', "The ticket has same id as parent id."

            # Recursive/Circular ticket check : Does ticket recursion goes too deep (as defined by 'default.max_depth' in 'trac.ini')?
            max_depth = self.config.getint('childtickets', 'default.max_depth', default=5)

            fam_tree = [ ticket.id, pid ]   # The 'family tree' already consists of this ticket id plus the parent

            for grandad in self._get_parent_id(pid):
                fam_tree.append(grandad)
                if ticket.id == grandad:
                    yield 'parent', "The tickets have a circular dependency upon each other : %s" % str(' --> '.join([ '#%s'%x for x in fam_tree]))
                if len(fam_tree) > max_depth:
                    yield 'parent', "Parent/Child relationships go too deep, 'max_depth' exceeded (%s) : %s" % (max_depth, ' - '.join([ '#%s'%x for x in fam_tree]))
                    break

            # Try creating parent ticket instance : it should exist.
            try:
                parent = Ticket(self.env, pid)
            
            except ResourceNotFound: 
                yield 'parent', "The parent ticket #%d does not exist." % pid

            else:

                # (NOTE: The following checks are checks on the parent ticket being defined in the 'parent' box rather than on
                # the child ticket actually being created. It is therefore possible to 'legally' create this child ticket but
                # then for the restrictions or type of the parent ticket to change - I have NOT restricted the possibility to
                # modify parent type after children have been assigned, however, further modifications to the children themselves
                # would then throw up some errors and force the users to re-set the child type.)

                # self.env.log.debug("TracchildticketsModule : parent.ticket.type: %s" % parent['type'])

                # Does the parent ticket 'type' even allow child tickets? 
                if not self.config.getbool('childtickets', 'parent.%s.allow_child_tickets' % parent['type']):
                    yield 'parent', "The parent ticket (#%s) has type %s which does not allow child tickets." % (pid,parent['type'])

                # It is possible that the parent restricts the type of children it allows.
                allowedtypes = self.config.getlist('childtickets', 'parent.%s.restrict_child_type' % parent['type'], default=[])
                if allowedtypes and ticket['type'] not in allowedtypes:
                    yield 'parent', "The parent ticket (#%s) has type %s which does not allow child type '%s'. Must be one of : %s." % (pid,parent['type'],ticket['type'],','.join(allowedtypes))

    
    # ITemplateStreamFilter methods
    def filter_stream(self, req, method, filename, stream, data):

        # Tickets will be modified to show the child tickets as a list under the 'Description' section.
        if filename == 'ticket.html':

            # Get the ticket info.
            ticket = data.get('ticket')

            # Modify ticket.html with sub-ticket table, create button, etc...
            # As follows:
            # - If ticket has no child tickets and child tickets are NOT allowed then skip.
            # - If ticket has child tickets and child tickets are NOT allowed (ie. rules changed or ticket type changed after children were assigned),
            #   print list of tickets but do not allow any tickets to be created.
            # - If child tickets are allowed then print list of child tickets or 'No Child Tickets' if non are currently assigned.
            # 
            if ticket and ticket.exists:

                # The additional section on the ticket is built up of (potentially) three parts: header, ticket table, buttons. These
                # are all 'wrapped up' in a 'div' with the 'attachments' id (we'll just pinch this to make look and feel consistent with any
                # future changes!)
                filter = Transformer('//div[@id="ticket"]')
                snippet = tag.div(id="attachments")

                # Are there any child tickets to display?
                childtickets = [ Ticket(self.env,n) for n in self.childtickets.get(ticket.id,[]) ]

                # (tempish) fix for #8612 : force sorting by ticket id
                childtickets = sorted(childtickets, key=lambda t: t.id)

                # Are child tickets allowed?
                childtickets_allowed = self.config.getbool('childtickets', 'parent.%s.allow_child_tickets' % ticket['type'])

                # If there are no childtickets and the ticket should not have any child tickets, we can simply drop out here.
                if not childtickets_allowed and not childtickets:
                    return stream

                # Our 'main' display consists of two divs.
                buttondiv = tag.div()
                tablediv = tag.div()

                # Test if the ticket has children: If so, then list in pretty table.
                if childtickets:

                    # trac.ini : Which columns to display in child ticket listing?
                    columns = self.config.getlist('childtickets', 'parent.%s.table_headers' % ticket['type'], default=['summary','owner'])

                    tablediv = tag.div(
                                tag.table(
                                    tag.thead(
                                        tag.tr(
                                            tag.th("Ticket",class_="id"),
                                            [ tag.th(s.title(),class_=s) for s in columns ])
                                        ),
                                    tag.tbody([ self._table_row(req,tkt,columns) for tkt in childtickets ]),
                                    class_="listing tickets",
                                    ),
                                tag.br(),
                                )

                # trac.ini : child tickets are allowed - Set up 'create new ticket' buttons.
                if childtickets_allowed:

                    # Can user create a new ticket? If not, just display title (ie. no 'create' button).
                    if 'TICKET_CREATE' in req.perm(ticket.resource):

                        # Always pass these fields
                        default_child_fields = (
                                tag.input(type="hidden", name="parent", value='#'+str(ticket.id)),
                                )

                        #Pass extra fields defined in inherit parameter of parent
                        inherited_child_fields = [
                                tag.input(type="hidden",name="%s"%field,value=ticket[field]) for field in self.config.getlist('childtickets','parent.%s.inherit' % ticket['type'])
                                ]

                        # If child types are restricted then create a set of buttons for the allowed types (This will override 'default_child_type).
                        restrict_child_types = self.config.getlist('childtickets','parent.%s.restrict_child_type' % ticket['type'],default=[])

                        if not restrict_child_types:
                            # trac.ini : Default 'type' of child tickets?
                            default_child_type = self.config.get('childtickets', 'parent.%s.default_child_type' % ticket['type'], default=self.config.get('ticket','default_type'))

                            # ... create a default submit button
                            submit_button_fields = (
                                    tag.input(type="submit",name="childticket",value="New Child Ticket",title="Create a child ticket"),
                                    tag.input(type="hidden", name="type", value=default_child_type),
                                    )
                        else:
                            submit_button_fields = [ tag.input(type="submit",name="type",value="%s" % ticket_type,title="Create a %s child ticket" % ticket_type) for ticket_type in restrict_child_types ]
                        buttondiv = tag.form(
                                    tag.div( default_child_fields, inherited_child_fields, submit_button_fields),
                                    method="get", action=req.href.newticket(),
                                    )

                snippet.append(tag.h2("Child Tickets",class_="foldable"))
                snippet.append(tag.div(tablediv, buttondiv))

                return stream | filter.after(snippet)

        return stream


    def _table_row(self, req, ticket, columns):
        # Is the ticket closed?
        ticket_class = ''
        if ticket['status'] == 'closed':
            ticket_class = 'closed'
        return tag.tr(
                tag.td(tag.a("#%s" % ticket.id, href=req.href.ticket(ticket.id), title="Child ticket #%s" % ticket.id, class_=ticket_class), class_="id"),
                [ tag.td(ticket[s], class_=s) for s in columns ],
                )

    def _get_parent_id(self, ticket_id):
        # Create a temp dict to hold direct child->parent relationships.
        parenttickets = {}
        for parent,childtickets in self.childtickets.items():
            for child in childtickets:
                parenttickets[child] = parent
        while ticket_id in parenttickets:
            yield parenttickets[ticket_id]
            ticket_id = parenttickets[ticket_id]

