# ChildTickets plugin

import re

from trac.core import *
from trac.ticket.api import ITicketManipulator
from trac.web.api import ITemplateStreamFilter, IRequestFilter
from trac.perm import IPermissionRequestor
from trac.ticket.model import Ticket

from genshi.builder import tag
from genshi.filters import Transformer

class TracchildticketsModule(Component):
    implements(ITicketManipulator, ITemplateStreamFilter, IRequestFilter)



    # IRequestFilter methods
    def pre_process_request(self, req, handler):

        # Get ticket relationships before processing anything.
        if req.path_info[0:8] == '/ticket/':
            cursor = self.env.get_db_cnx().cursor()
            cursor.execute('SELECT ticket,value FROM ticket_custom WHERE name="parent"')
            self.env.childtickets = {}
            for child,parent in cursor.fetchall():
                if parent and re.match('#\d+',parent):
                    parent = int(parent.lstrip('#'))
                    self.env.childtickets.setdefault(parent,[]).append(child)
        return handler

    def post_process_request(self, req, template, data, content_type):
        return (template, data, content_type)



    # ITicketManipulator methods
    def prepare_ticket(self, req, ticket, fields, actions):
        pass
    
    def validate_ticket(self, req, ticket):

        # Don't allow ticket to be 'resolved' if any child tickets are still open.
        if req.args.get('action') == 'resolve':
            for t in self.env.childtickets.get(ticket.id,[]):
                if Ticket(self.env,t)['status'] != 'closed':
                    yield None, 'Cannot resolve ticket while child ticket (#%s) is still open.' % t

        # Check if the 'parent' field is being used.
        if ticket.values.get('parent'):

            # Is it of correct 'format'?
            if not re.match('^#\d+',ticket.values.get('parent')):
                yield None, "The parent id must be of the form '#id' where 'id' is a valid ticket id."

            parent = int(ticket.values.get('parent').lstrip('#'))

            # Try creating parent ticket instance : it should exist.
            try:
                Ticket(self.env, parent)
            except:
                yield None,"The parent ticket #%d does not exist." % parent

            # Check we're not being daft and setting own id as parent (this could still be poss. if you 'guess' the id at creation time!)
            if ticket.id and parent == ticket.id:
                yield None, "The ticket has same id as parent id."

            # TODO: Add a recursive ticket check, subject to a general limit (trac.ini) which has a default value of, say 3.
            # yield None, "The ticket recursion is too deep (%s)" % max_depth


    
    # ITemplateStreamFilter methods
    def filter_stream(self, req, method, filename, stream, data):

        # Tickets will be modified to show the child tickets as a list under the 'Description' section.
        if filename == 'ticket.html':

            # Get the ticket info.
            ticket = data.get('ticket')

            # self.env.log.debug("XXXX : ITemplateStreamFilter.filter_stream() : ticket.type: %s" % ticket['type'])
            
            # Modify ticket.html with sub-ticket table, create button, etc...
            if ticket and ticket.exists and self.config.getbool('childtickets', 'parent.%s.allow_child_tickets' % ticket['type']):

                filter = Transformer('//div[@class="description"]')
                snippet = tag()
                
                # trac.ini : Which columns to display in child ticket listing?
                columns = self.config.getlist('childtickets', 'parent.%s.table_headers' % ticket['type'], default=['summary','owner'])

                # trac.ini : Default milestone of child tickets?
                default_child_milestone = ticket['milestone'] if self.config.getbool('childtickets', 'parent.%s.inherit_milestone' % ticket['type']) else self.config.get('ticket', 'default_milestone')

                # trac.ini : Default 'type' of child tickets?
                default_child_type = self.config.get('childtickets', 'parent.%s.default_child_type' % ticket['type'])

                # Are there any child tickets to display?
                childtickets = [ Ticket(self.env,n) for n in self.env.childtickets.get(ticket.id,[]) ]

                # Can user create a new ticket? If not, just display title (ie. no 'create' button).
                if 'TICKET_CREATE' in req.perm(ticket.resource):
                    snippet.append(tag.div(
                        tag.form(
                            tag.div(
                                tag.input(type="submit", name="childticket", value="Create", title="Create a child ticket"),
                                tag.input(type="hidden", name="parent", value='#'+str(ticket.id)),
                                tag.input(type="hidden", name="milestone", value=default_child_milestone),
                                tag.input(type="hidden", name="type", value=default_child_type),
                                class_="inlinebuttons"),                            
                            method="get", action=req.href.newticket(),
                            ),
                        tag.h3("Child Tickets",id="comment:child_tickets"),
                        ))
                else:
                    snippet.append(tag.div(tag.h3("Child Tickets",id="comment:child_tickets")))

                # Test if the ticket has children: If so, then list in pretty table.
                if not childtickets:
                    snippet.append(tag.div(tag.p("NO SUB-TICKETS.")))
                else:
                    snippet.append(
                            tag.div(
                                tag.table(
                                    tag.thead(
                                        tag.tr(
                                            tag.th("Ticket",class_="id"),
                                            [ tag.th(s.title(),class_=s) for s in columns ])
                                        ),
                                    tag.tbody([ self._table_row(req,tkt,columns) for tkt in childtickets ]),
                                    class_="listing tickets",
                                    ),
                                )
                            )

                return stream | filter.append(snippet)

        return stream

    def _table_row(self, req, ticket, columns):

        # Is the ticket closed?
        ticket_class = 'closed' if ticket['status'] == 'closed' else ''

        return tag.tr(
                tag.td(tag.a("#%s" % ticket.id, href=req.href.ticket(ticket.id), title="Child ticket #%s" % ticket.id, class_=ticket_class), class_="id"),
                [ tag.td(ticket[s], class_=s) for s in columns ],
                )
