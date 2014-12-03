"""
XBlock to display SCORM content.
Right now, this is targeting the SCORM 2014 API.

FIXME: No consideration has been given to security. Don't let untrusted staff use this.
"""

# The path that SCORM content is stored in
# FIXME: nasty
SCORM_PATH = '/edx/app/edxapp/edx-platform/scorm'

import os
import os.path
import pkg_resources
from threading import Lock

from xblock.core import XBlock
from xblock.fields import Scope, BlockScope, String, Dict  #, Field
from xblock.fragment import Fragment
#from xblock.runtime import KeyValueStore


class SCORMXBlock(XBlock):
    """
    XBlock wrapper for SCORM content objects
    """

    scorm_dir = String(help="Directory that the SCORM content object is stored in", default=None, scope=Scope.settings)

    lock = Lock()
    scorm_data = Dict(
        scope=Scope.user_state,
        help="Temporary storage for SCORM data",
    )

    # SCORM 2004 fields
    cmi_completion_status = String(default='unknown', scope=Scope.user_state)
    # cmi_entry = String(default=TODO, scope=Scope.user_state)

    def __init__(self, *args, **kwargs):
        XBlock.__init__(self, *args, **kwargs)

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def studio_view(self, context=None, scorm_path=SCORM_PATH):
        try:
            try:
                ls = os.listdir(scorm_path)
            except OSError, e:
                return Fragment(u"ERROR: couldn't read SCORM directory (%s). The full error is '%s'." % (scorm_path, e))

            # make a list of available SCORMs
            scorms = []
            for dirname in ls:
                # check if there is a manifest
                if os.path.isfile(os.path.join(scorm_path, dirname, 'imsmanifest.xml')):
                    scorms.append(dirname)

            frag = Fragment(content=u'<h2>Available SCORMs</h2><ul>')
            # TODO push all of this to a Mako/jinja template somewhere

            if scorms:
                for s in scorms:
                    # FIXME: These URLs probably work for Articulate Storyline content and nothing else
                    # We should be looking at the manifest file to find the base URL
                    # FIXME: these preview links don't load the SCORM API. It might be easier to factor out the student_view and use it here.
                    url = '/scorm/%s/index_lms_html5.html' % (dirname)

                    checked = ''
                    if self.scorm_dir == dirname:
                        checked = ' checked'

                    frag.add_content(u"<input type='radio' name='scorm_dir' value='%s'%s> %s (<a href='%s'>preview</a>)<br />" % (s, checked, s, url))
                frag.add_content(u"<a href='#' class='button action-primary save-button'>Save</a>")
            else:
                frag.add_content(u"There isn't any SCORM content available. Please check that you've unzipped your content into the '%s' directory and try again." % scorm_path)

            frag.add_javascript(self.resource_string("static/studio.js"))
            frag.initialize_js('SCORMStudioXBlock')
        except Exception, e:
            # This is horrible and nasty, but this way we actually get some debug info.
            import traceback
            print traceback.print_exc()
            frag = Fragment(unicode(e))

        return frag

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Called when submitting the form in Studio.
        """
        self.scorm_dir = data.get('scorm_dir')

        return {'result': 'success'}

    @XBlock.json_handler
    def sco_req(self, data, suffix=''):
        """
        JSON request from the student's SCO.

        This is multiplexed to handle all of the GetValue/SetValue/etc requests
        through one entry point.
        """

        assert 'method' in data.keys(), 'not implemented'  # should return a 'bad request' to SCO

        method = data['method']

        if method == 'getValue':
            assert 'name' in data.keys(), 'TODO return "bad request"'
            result = self.model.get(data['name'])
        elif method == 'setValue':
            assert 'name' in data.keys(), 'TODO return "bad request"'
            assert 'value' in data.keys(), 'TODO return "bad request"'
            result = self.model.set(data['name'])
        else:
            print 'not implemented method %s' % method
            assert False, 'not implemented'  # should return a 'not implemented' to SCO

        if hasattr(result, 'error_code'):
            # it's an error
            error_code = result.error_code
            value = result.value
        else:
            # it's a success with value
            error_code = 0
            value = result

        # print 'FIXME STUB: sco_req %s' % data
        # self.scorm_dir = data.get('scorm_dir')

        return {'result': 'success', 'error_code': error_code, 'value': value}

    def load_resource(self, resource_path):
        """
        Gets the content of a resource
        """
        resource_content = pkg_resources.resource_string(__name__, resource_path)
        return unicode(resource_content)

    def student_view(self, context=None):
        if self.scorm_dir is None:
            return Fragment(u"<h1>Error</h1><p>There should be content here, but the course creator has not configured it yet. Please let them know.</p><p>If you're the course creator, you need to go into edX Studio and hit Edit on this block. Choose a SCORM object and click Save. Then, the content should appear here.</p>")

        # TODO it might be nice to confirm that the content is actually present

        # TODO at this point, we need to load the manifest to find the entry point to point the iframe at
        url = '/scorm/%s/index_lms.html' % self.scorm_dir
        html_str = pkg_resources.resource_string(__name__, "templates/scorm.html")
        frag = Fragment(unicode(html_str).format(self=self, url=url))

        frag.add_javascript(self.resource_string("public/rte.js"))
        frag.add_javascript(self.resource_string("public/SCORM_API_wrapper.js"))
        frag.add_javascript(self.resource_string("public/frame.js"))
        frag.initialize_js('SCORMXBlock')

        return frag

    @XBlock.json_handler
    def scorm_set_value(self, data, suffix=''):
        """
        SCORM API handler to receive data from the SCO
        
        Just calls scorm_commit(), since the current js API
        handler caches data client-side, and it shouldn't 
        actually get set until commit() is called.
        """
        return self.scorm_commit(data,suffix)

    @XBlock.json_handler
    def scorm_get_value(self, data, suffix=''):
        """
        SCORM API handler to get data from the LMS
        """
        return self.scorm_data

    @XBlock.json_handler
    def scorm_clear(self, data, suffix=""):
        """
        Custom (not in SCORM API) function for emptying xblock scorm data
        """
        del(self.scorm_data)

    @XBlock.json_handler
    def scorm_dump(self, data, suffix=""):
        """
        Custom (not in SCORM API) function for viewing xblock scorm data
        """
        return self.scorm_data

    @XBlock.json_handler
    def scorm_test(self, data, suffix=""):
        """
        Custom (not in SCORM API) function for testing frequent writes in a single instance.
        """
        del(self.scorm_data)
        for k, v in data:
            self.scorm_data[k] = v

     ##
     # The rest of these aren't really implemented yet
     ##
    @XBlock.json_handler
    def scorm_commit(self, data, suffix=""):
        """
        SCORM API handler to permanently store data in the LMS
        """
        ## TODO: Locks no longer necessary?
        self.lock.acquire()
        try:
            scorm_data = self._field_data.get(self,"scorm_data")
        except KeyError:
            scorm_data = {}
        scorm_data.update(data)
        self._field_data.set(self,"scorm_data", scorm_data)
        self.lock.release()

    @XBlock.json_handler
    def scorm_finish(self, data, suffix=""):
        """
        SCORM API handler to wrap up communication with the LMS
        """
        return self.publish_scorm_data(data)

    def publish_scorm_data(self,data):
        """
        Emit relevant events to the edx analytics system
        """
        return True

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("SCORM XBlock",
             """<xb_scorm scorm_dir='USBS Referencing'/>"""),
             # """<xb_scorm scorm_dir='USBS Referencing Tincan'/>"""),
        ]

    # SCORM 2004 data model
    class SCORMError(object):
        def __init__(self, error_code, value=''):
            self.error_code = error_code
            self.value = value

    def get(self, key):
        if key == 'cmi.completion_status':
            return self.cmi_completion_status
        elif key == 'cmi.mode':
            return 'normal'
        elif key == 'cmi.success_status':
            return 'unknown'
        elif key == 'cmi.suspend_data':
            return SCORMError(403)
        elif key == 'cmi.scaled_passing_score':
            assert False, 'TODO you need to modify cmi.success_status to handle this value'
        elif key == 'cmi.completion_threshold':
            assert False, 'TODO you need to modify cmi.completion_status to handle this value'
        else:
            print "SCORM2004::get('%s'): unknown key" % key
            assert False, 'get return not implemented'

    def set(self, key, value):
        if key == 'cmi.completion_status':
            self.cmi_completion_status = value  # TODO check the value we're trying to write
        elif key == 'cmi.exit':  # write-only
            if value == 'suspend':
                self.cmi_entry = 'resume'
            # elif value == 'logout':
                # self.cmi_entry = '
            else:
                assert False, 'TODO not implemented verb %s for cmi.exit' % value
        elif key == 'cmi.scaled_passing_score':
            assert False, 'TODO you need to modify cmi.success_status to handle this value'
        elif key == 'cmi.completion_threshold':
            assert False, 'TODO you need to modify cmi.completion_status to handle this value'
        # elif key == 'cmi.suspend_data':
            # assert False, 'TODO suspend_data'
        else:
            print "SCORM2004::set('%s'): unknown key" % key
            assert False, 'set return not implemented'


class SCORMXBlockStudioHack(SCORMXBlock):
    '''
    Wrapper for SCORMXBlock that shows the studio view (for development under
    the XBlock Workbench).

    FIXME: this is a nasty hack that probably isn't necessary. If you know how
    to do this better, please let me (ian@mutexlabs.com) know...

    Another alternative would be to pass in a flag in the scenario XML that
    forces studio display.
    '''

    def student_view(self, *args, **kwargs):
        # By default, SCORM content is served out of SCORM_PATH. In the Workbench this might not exist, so we override.
        return SCORMXBlock.studio_view(self, scorm_path=os.path.abspath('./scorm/'), *args, **kwargs)

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("SCORM XBlock (Studio view)",
             """<xb_scorm_studiohack scorm_dir='USBS Referencing'/>"""),
             # """<xb_scorm_studiohack scorm_dir='USBS Referencing Tincan'/>"""),
        ]
