#!/usr/bin/python

import cgi
try:
    import json
except ImportError:
    import simplejson as json
import re
import subprocess
import datetime
import threading
import os
import logging
import sys

types = [
    {'call': 'AssertEquals'},
    {'call': 'AssertEqualObjects'},
]

semapthore = threading.Semaphore()

class MyHandler():
    def __init__(self, path, params):
        self.path = path
        self.params = params

    def do_GET(self):
        path = self.path
        vars = self.params
        return self.do_request(path, 'GET', vars)

    def format_tests2(self, tests, solution):
        global types
        res = ''
        resultList = []
        testCases = tests.splitlines()
        line_number = 11 + len(solution.splitlines()) #the first test line
        for testCase in testCases:
            testCase = testCase.strip()
            type = None
            if not testCase.startswith('//'):
                for t in types:
                    if t['call'] in testCase:
                        type = t
                        break
            if type:
                exp = '([^,]+)'
                parse_exp = '%s\(%s *, *%s\);' % (type['call'], exp, exp)
                mo = re.compile(parse_exp).search(testCase)
                if mo:
                    call = mo.group(1)
                    expected = mo.group(2)
                    resultList.append({
                        'call': call,
                        'expected': expected,
                        'received': expected,
                        'correct': None,
                        'line': line_number,
                        'type': type
                        })
                    res += '%s(%s, %s);\n' % (type['call'], call, expected)
                else:
                    res += '%s\n' % testCase
            else:
                res += '%s\n' % testCase
            line_number += 1
        logging.info('res:\n%s\nresultList: %s' % (res, resultList))
        return res, resultList

    def do_request(self, path, method, vars):
        self.do_request2(path=path, method=method, vars=vars)

    def do_request2(self, path, method, vars):
        print "Content-type: application/json\n\n";
        #Parse out the posted JSON data
        jsonrequest = vars.get('jsonrequest', '{}')
        if type(jsonrequest) == type([]):
            jsonrequest = jsonrequest[0]
        requestDict = json.loads(jsonrequest)
        solution = requestDict.get('solution').strip()
        tests = requestDict.get('tests').strip()
        formattedTests, resultList = self.format_tests2(tests, solution)

        #Update the objective C test file by pasting in the solution code and tests.
        code = \
'''#import <Foundation/Foundation.h>
#import <stdio.h>

%(solution)s
void fjskdjhgkjhgskjghkjsdahlksdjh() {
}

//replaces all occurences with another occurence
char *str_replace(char * orig, char * search, char * replace){
    if (!strstr(orig, search)) {
        return orig;
    }
    char * pos = "\\0";
    char * buffer = malloc(strlen(orig) * 2);
    buffer[0] = '\\0';
    while (strstr(orig, search)) {
        pos = strstr(orig, search);
        strncpy(buffer + strlen(buffer), orig, pos - orig);
        strcat(buffer, replace);
        pos += strlen(search);
        orig = pos;

    }
    return strcat(buffer, pos);
}

NSString * toString(NSValue *value) {
    if (strcmp([value objCType], "i") == 0) {
        int valPtr;
        [value getValue:&valPtr];
        return [NSString stringWithFormat:@"%%i", valPtr];
    }
    if (strcmp([value objCType], "f") == 0) {
        float valPtr;
        [value getValue:&valPtr];
        return [NSString stringWithFormat:@"%%g", valPtr];
    }
    if (strcmp([value objCType], "d") == 0) {
        double valPtr;
        [value getValue:&valPtr];
        return [NSString stringWithFormat:@"%%g", valPtr];
    }
    if (strcmp([value objCType], "@") == 0) {
        int valPtr;
        [value getValue:&valPtr];
        return [NSString stringWithFormat:@"\\\\\\"%%@\\\\\\"", valPtr];
    }
    void * valPtr;
    [value getValue:&valPtr];
    NSString * format = [NSString stringWithFormat:@"%%%%%%s", [value objCType]]; 
    return [NSString stringWithFormat:format, valPtr];
}
#define AssertEquals(a, b) \\
    do { \\
        __typeof__(a) avalue = (a); \\
        __typeof__(b) bvalue = (b); \\
        NSValue *aencoded = [NSValue value:&avalue withObjCType: @encode(__typeof__(avalue))]; \\
        NSValue *bencoded = [NSValue value:&bvalue withObjCType: @encode(__typeof__(bvalue))]; \\
        int __result = 0; \\
        if (@encode(__typeof__(avalue)) != @encode(__typeof__(bvalue))) { \\
            __result = 0; \\
        } else { \\
            if ([aencoded isEqualToValue:bencoded]) { \\
                __result = 1; \\
            } \\
        } \\
        [results addObject:[NSArray arrayWithObjects: \\
                        __result ? @"true" : @"false", \\
                        [NSString stringWithFormat:@"%%@", toString(aencoded)], \\
                        [NSString stringWithFormat:@"%%@", toString(bencoded)], \\
                        [NSString stringWithFormat:@"AssertEquals(%%s, %%s);", str_replace(#a,"\\"", "\\\\\\""),\\
                            str_replace(#b,"\\"", "\\\\\\"")], nil]]; \\
    } while(0);

NSMutableArray * testMethod()
{   
    //Paste the code under test here.
    //End of code under test
NSMutableArray *results = [[NSMutableArray alloc] init];
    //Paste the tests in here
%(tests)s
    //End of tests
    return results;
}
int main( int argc, const char *argv[] ) {
    NSAutoreleasePool * pool = [[NSAutoreleasePool alloc] init];
    NSMutableArray * results = testMethod();

    NSEnumerator *enumerator = [results objectEnumerator];

    printf("{\\"results\\": [");
    id row;
    int first = 1;
    int allSolved = 1;
    while ( (row = [enumerator nextObject]) ) {
        NSString *correct = [row objectAtIndex:0];
        NSString *expected = [row objectAtIndex:1];
        NSString *received = [row objectAtIndex:2];
        NSString *call = [row objectAtIndex:3];

        if (allSolved && (strcmp([correct cString], "true") != 0)) {
            allSolved = 0;
        }
        if (!first) printf(",");
        else first = 0;
        printf("{\\"expected\\": \\"%%s\\", \\"received\\": \\"%%s\\", \\"call\\": \\"%%s\\", \\"correct\\": %%s}",
            [expected cString], [received cString], [call cString], [correct cString]);
    }
    printf("], \\"solved\\": %%s, \\"printed\\": \\"\\"}", (allSolved ? "true" : "false"));

    [pool release];

    return 0;
}
''' % {'solution': solution, 'tests': formattedTests}
        now = datetime.datetime.now()
        uid = '%s_%06d' % (now.strftime('%Y%m%d_%H%M%S'), now.microsecond)
        src_file = 'ObjCSolution_%s.m' % uid
        src_path = '/tmp/%s' % src_file
        binary_path = '/tmp/ObjCSolution_%s.out' % uid
        result_path = '/tmp/ObjCSolution_%s.result' % uid
        f = open(src_path, 'w')
        f.write(code)
        f.close()
        if os.path.exists(binary_path):
            os.remove(binary_path)
        #Execute the xcodebuild commandline options and read the results
        # xcodebuild -target Test
        cmd = '/usr/bin/c99 %s -o %s `gnustep-config --objc-flags` -lgnustep-base' % (
            src_path, binary_path)
        cmd = ['/bin/bash', '-c', "(%s ; true)" % cmd]
        compileResult = self.exec_command_and_get_output(cmd)
        if os.path.exists(binary_path):
            cmd = ['/bin/bash', '-c', "(%s ; true)" % binary_path]
            result = self.exec_command_and_get_output(cmd)
        else:
            result = ''

        # Create a valid json respose based on the xcodebuild results or error returned.
        compile_warnings_and_errors = self.grep(compileResult, '%s:' % src_file)
        compile_warnings_and_errors = self.correct_line_numbers(compile_warnings_and_errors, src_file)
        compile_errors = self.grep(compileResult, '%s:[0-9]+: error:' % src_file)
        compile_errors = self.correct_line_numbers(compile_errors, src_file)
        if compile_errors:
            jsonResult = {'errors': compile_warnings_and_errors[0:450]}
        else:
            #it probably compiled, look for test results
            if result and result[0] == '{' and result[-1] == '}':
                jsonResult = json.loads(result)
            else: #other unecpected result
                s = '%s\n%s' % (compile_warnings_and_errors, result)
                jsonResult = {'errors': s[0:450]}
        s = json.dumps(jsonResult)
        if len(s) > 400:
            compile_warnings_and_errors = ''
        jsonResult['printed'] = compile_warnings_and_errors[0:450-len(s)]
        # Return the results
        s = json.dumps(jsonResult)
        print s
        f = open(result_path, 'w')
        f.write(s)
        f.close()
        return

    def correct_line_numbers(self, string, src_file):
        result = ''
        for line in string.split('\n'):
            mo = re.compile('^(.*%s:)([0-9]+)(:.*)$' % src_file).search(line)
            if mo:
                lineno = int(mo.group(2)) - 3
                line = '%s%s%s' % (mo.group(1), lineno, mo.group(3))
            if result:
                result += '\n'
            result += '%s' % line
        return result
        
    def grep(self, string, pattern):
        matches = ''
        for line in string.split('\n'):
            match = (pattern in line)
            if not match:
                try:
                    match = True if re.compile(pattern).search(line) else False
                except:
                    pass
            if match:
                matches += str(line) + '\n'
        return matches

    def exec_command_and_get_output(self, cmd):
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd='/tmp')
        s = child.communicate()[0]
        return s

    def do_POST(self):
        ctype = os.environ.get('CONTENT_TYPE', '')
        if ctype == 'multipart/form-data':
            postvars = {}
            #postvars = cgi.parse_multipart(sys.stdin, pdict)
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(os.environ.get('CONTENT_LENGTH', 0))
            postvars = cgi.parse_qs(sys.stdin.read(length), keep_blank_values=False)
        else:
            postvars = {}
        return self.do_request(self.path, 'POST', postvars)

def main():
    path = os.environ.get('SCRIPT_NAME','').replace('/cgi-bin/', '')
    params = cgi.parse_qs(os.environ.get('QUERY_STRING',''), keep_blank_values=False)
    h = MyHandler(path, params)
    if os.environ.get('REQUEST_METHOD','') == 'GET':
        h.do_GET()
    else:
        h.do_POST()

main()

