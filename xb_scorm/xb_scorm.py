"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources

from xblock.core import XBlock
from xblock.fields import Scope, BlockScope, String, Dict, Field
import xblock.fields
from xblock.fragment import Fragment
from xblock.runtime import KeyValueStore

# BHS additions
import sys
import lxml.etree, time
import os.path
from cStringIO import StringIO
from threading import Lock
import json
import copy
import inspect


from xblock.fields import NO_CACHE_VALUE,  EXPLICITLY_SET, NO_GENERATED_DEFAULTS


def format_dict(d):
    """
    Return dict as a string of '\n\tKEY = VALUE' pairs
    """
    if len(d) == 0 :
        vals = "  EMPTY"
    else:
        vals = "  "+ ",  ".join([ k + " = " + v for k,v in d.items() ])
    return "\n  FIELD CONTENTS: " + vals
        
def dbg(xblock,label,data=None):
    """
    Print debug message identified by instance@time
    """
    tstamp = time.time()
    blockaddr = str(id(xblock))
    fieldaddr = "no field yet"
    
    # Caller history
    # c.f. http://stackoverflow.com/questions/2654113/
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2); callers = []
    stackidx = len(calframe) - 1
    skipidx = 0
    ## skip most recent calls to self
    while calframe[skipidx][3] == "dbg":
        skipidx += 1
    while stackidx >= skipidx:
            callers.append(calframe[stackidx][3])
            stackidx -= 1
    callers =  "->".join(callers)
    
    if None in ( xblock, data ):
        msg = ""
    elif type(data) == LoggingDict:
        fieldaddr = id(data)
        msg = format_dict(data.get_raw(xblock))
    elif type(data) == dict:
        msg = format_dict(data)
    else:
        msg = str(data)
        
    stamp =    "\n{}\nB {:<10}  F {:<15}  @ {:<15}".format(
        callers,
        blockaddr,
        fieldaddr,
        tstamp
    )
    
    # Log to Django's stdout
    sys.stderr.write("{}{:<30}{}\n".format(stamp, label, msg))
    
    # ...and optionally an AJAX handler
    return {"{} {}".format(stamp,label) : msg}
     
     
class LoggingDict(Dict):
    """
    Superclass of the Dict that logs info about sets and gets for debugging
    """    

    def get_raw(self,xblock):
        """
        Basically Dict.__get__(), but no cache changes or logging
        """
        if xblock is None:
            return self
            
        # Some gymnastics are required here, because the normal
        # Dict.__get__() calls xblock.field_data.has(), which calls ._key(),
        # which calls ._getfield(), which triggers does a getattr() for the 
        # field, which triggers __get__() again (though with no xblock 
        # passed, so it returns self and avoids a 
        value = getattr(xblock, '_field_data_cache', {}).get(self.name, NO_CACHE_VALUE)
        if value == NO_CACHE_VALUE:
            try:
                key = KeyValueStore.Key(
                    scope = self.scope,
                    user_id=xblock.scope_ids.user_id,
                    block_scope_id=xblock.scope_ids.usage_id,
                    field_name=self.name,
                ) 
                if (xblock._field_data._kvs.has(key)):
                    value = self.from_json(xblock._field_data.get(xblock, self.name))  
                else:
                    value = self.default
            except KeyError:
                value = self.default  
        return value
        
    def dbg(self,xblock,label,data=None):
        """
        Wrapper for dbg(), which includes the field's content by default
        """
        if data is None:
            data = self
        return dbg(xblock,label,data)
        
        
    
    def __set__(self,xblock,value):
        self.dbg(xblock,"FIELD SET for %s starting" % value)
        super(LoggingDict,self).__set__(xblock,value)
        self.dbg(xblock,"FIELD SET for %s returning" % value)
        
    def _set_cached_value(self, xblock, value):
        self.dbg(xblock,"FIELD CACHE SET for %s starting" % value)
        super(LoggingDict,self)._set_cached_value(xblock,value)
        self.dbg(xblock,"FIELD CACHE SET for %s returning" % value)
        
    def __get__(self, xblock, xblock_class):
        self.dbg(xblock,"FIELD GET starting")
        ret = super(LoggingDict,self).__get__(xblock,xblock_class)
        self.dbg(xblock,"FIELD GET returning %s" % ret)
        return ret
        
    def _get_cached_value(self, xblock):
        self.dbg(xblock,"FIELD CACHE GET starting")
        ret = super(LoggingDict,self)._get_cached_value(xblock)
        self.dbg(xblock,"FIELD CACHE GET returning %s" % ret)
        return ret
        

class XblockSCORM(XBlock):
    """
    XBlock wrapper for SCORM content objects
    """
    scorm_data = LoggingDict(
        scope=Scope.user_state,
        help="Temporary storage for SCORM data",
    )      
        
    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self,context=None):
        scorm_dir = os.path.join("static","scorm","exe1")
        scorm_index = os.path.join(scorm_dir,"index.html")
        scorm_html = self.resource_string(scorm_index)
        root_el = lxml.etree.HTML(str(scorm_html))
        js_filenames = []
        for js_el in root_el.xpath("//script[@type='text/javascript' and @src != '']"):
            js_filenames.append(js_el.get("src"))
            js_el.getparent().remove(js_el)
    
        css_filenames = []
        for css_el in root_el.xpath("//link[@rel='stylesheet' and @href != '']"):
            css_filenames.append(css_el.get("href"))
            css_el.getparent().remove(css_el)
        
        html = lxml.etree.tostring(root_el,encoding=unicode,method="html")
        frag = Fragment(html)
        for fn in js_filenames:
            frag.add_javascript(self.resource_string(os.path.join(scorm_dir,fn)))
        for fn in css_filenames:
            frag.add_css(self.resource_string(os.path.join(scorm_dir,fn)))
        #frag.add_javascript(self.resource_string("static/js/src/scorm-api-wrapper/src/JavaScript/SCORM_API_wrapper.js"))
        frag.add_javascript(self.resource_string("static/js/src/xb_scorm.js"))
        frag.initialize_js('XblockSCORM')
        
        #import pdb; pdb.set_trace()
        return frag
        
    def save(self):
        """
        Logging wrapper around xblock.save()
        """
        log = {}
        log.update(dbg(self,"SAVE START"))
        super(XblockSCORM,self).save()
        log.update(dbg(self,"SAVE END"))
        return log
            
    @XBlock.json_handler
    def scorm_set_value(self, data, suffix=''):
        """
        SCORM API handler to report data to the LMS
        """   
        log = {}
        log.update(dbg(self,"SCORM SET for %s starting" % data))
        scorm_data = copy.deepcopy(self.scorm_data)
        log.update(dbg(self,"SCORM SET for %s copied %s" % (data,scorm_data)))
        scorm_data.update(data)
        log.update(dbg(self,"SCORM SET for %s updated to %s" % (data,scorm_data)))
        self.scorm_data = scorm_data
        log.update(dbg(self,"SCORM SET for %s done" % data))
        return log

    @XBlock.json_handler
    def scorm_get_value(self, data, suffix=''):
        """
        SCORM API handler to get data from the LMS
        """
        dbg(self,"SCORM GET for %s starting" % data)
        ret = self.scorm_data
        dbg(self,"SCORM GET for %s returning %s" % (data,ret))
        return ret
        
    @XBlock.json_handler
    def scorm_clear(self,data,suffix=""):
        """
        Custom (not in SCORM API) function for emptying xblock scorm data
        """
        log = {}
        log.update(dbg(self,"CLEAR starting"))
        del(self.scorm_data)
        log.update(dbg(self,"CLEAR returning"))
        return log
        
    @XBlock.json_handler
    def scorm_dump(self,data,suffix=""):
        """
        Custom (not in SCORM API) function for viewing xblock scorm data
        """
        # Get the data without triggering __get__
        data = self.__class__.__dict__["fields"]["scorm_data"]
        return dbg(self,"DUMP",data)

    @XBlock.json_handler
    def scorm_test(self,data,suffix=""):
        """
        Custom (not in SCORM API) function for testing frequent writes in a single instance.
        """
        del(self.scorm_data)
        log = {}
        log.update(dbg(self,"TEST starting"))
        for k,v in data:
            self.scorm_data[k] = v
        log.update(dbg(self,"TEST returning"))
        return log
        
     ##   
     # The rest of these aren't really implemented yet
     ##
    @XBlock.json_handler
    def scorm_commit(self, data, suffix=""):
        """
        SCORM API handler to permanently store data in the LMS
        """
        return self.publish_scorm_data(data)
       
    @XBlock.json_handler
    def scorm_finish(self, data, suffix=""):
        """
        SCORM API handler to wrap up communication with the LMS
        """
        return self.publish_scorm_data(data)

    def publish_scorm_data(self,data):
        return
        

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("XblockSCORM",
             """<vertical_demo>
                <xb_scorm/>
                </vertical_demo>
             """),
        ]
        
if __name__ == "__main__":
    print "DONE"
