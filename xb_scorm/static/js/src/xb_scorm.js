/* Javascript for XblockSCORM. */
    
function XblockSCORM(runtime, element) {	
    function report(data) {
        for (var key in data) {
            console.log("Data returned from server: " + key + " = " + data[key]);
        }
    }
    function SCORM_API() {
        this.buffer = {}
        this.clear_buffer = function() {
            this.buffer = {} ;  
        }
        this.LMSInitialize = function() {
            console.log("LMSInitialize")
            this.clear_buffer();
            return "true"; 
        }
        this.LMSFinish = function() {
            console.log("LMSFinish");
            var handlerUrl = runtime.handlerUrl( element,'scorm_finish');
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify({}),
                success: report,
            });
            return "true";   
        }
        this.LMSGetValue = function(cmi_element) {
            console.log("Getvalue for " + cmi_element);
            var data = cmi_element ;
            var handlerUrl = runtime.handlerUrl( element,'scorm_get_value');
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify(data),
                success: report,
            });
            return "true";
        }
        this.LMSSetValue = function(cmi_element,value) {
            console.log("LMSSetValue " + cmi_element + " = " + value);
            this.buffer[cmi_element] = value ;
            // TODO: handle failure at all
            return "true";
        }        	
        this.LMSCommit = function() {
            console.log("LMSCommit");
            var handlerUrl = runtime.handlerUrl( element,'scorm_set_value');
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify(this.buffer),
                context: this,
                success: function() { 
                    this.clear_buffer();
                    report(); 
                },
            });
            return "true";
        }
        this.LMSGetLastError = function() { 
            console.log("GetLastError");
            return "0";
        }
        this.LMSGetErrorString = function(errorCode) {
            console.log("LMSGetErrorString");
            return "Some Error";
        }
        this.LMSGetDiagnostic = function(errorCode) {
            console.log("LMSGetDiagnostic");
            return "Some Diagnostic";
        }        
        this.scorm_clear = function() {
            console.log("Clear");
            var handlerUrl = runtime.handlerUrl( element,'scorm_clear');
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify({}),
                success: report,
            });
        }
        this.scorm_dump = function() {
            console.log("Dump");
            var handlerUrl = runtime.handlerUrl( element,'scorm_dump');
            $.ajax({
                type: "POST",
                url: handlerUrl,
                data: JSON.stringify({}),
                success: report,
            });
        }
    }

    $(function ($) {
        API = new SCORM_API();
        console.log("Initial SCORM data...");
        API.scorm_dump();
    });
}
