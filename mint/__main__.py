
import os
import time
import fnmatch
from cStringIO import StringIO

from mint import Loader, tokenizer
from .ast_printer import Printer


def all_files_by_mask(mask):
    for root, dirs, files in os.walk('.'):
        for basename in files:
            if fnmatch.fnmatch(basename, mask):
                filename = os.path.join(root, basename)
                yield filename


def render_templates(*templates, **kw):
    loader = kw['loader']
    for template_name in templates:
        result = loader.get_template(template_name).render()
        if result:
            open(template_name[:-4]+'html', 'w').write(result)


def iter_changed(interval=1):
    mtimes = {}
    while 1:
        for filename in all_files_by_mask('*.mint'):
            try:
                mtime = os.stat(filename).st_mtime
            except OSError:
                continue
            old_time = mtimes.get(filename)
            if old_time is None:
                mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                mtimes[filename] = mtime
                yield filename
        time.sleep(interval)


if __name__ == '__main__':
    import datetime
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-c', '--code', dest='code', action='store_true',
                      default=False,
                      help='Show only python code of compiled template.')
    parser.add_option('-t', '--tokenize', dest='tokenize', action='store_true',
                      default=False,
                      help='Show tokens stream of template.')
    parser.add_option('-r', '--repeat', dest='repeat',
                      default=0, metavar='N', type='int',
                      help='Try to render template N times and display average time result.')
    parser.add_option('-p', '--pprint', dest='pprint', action='store_true',
                      default=False,
                      help='Turn pretty print on.')
    parser.add_option('-m', '--monitor', dest='monitor', action='store_true',
                      default=False,
                      help='Monitor current directory and subdirectories for changes in mint files. '
                           'And render corresponding html files.')
    (options, args) = parser.parse_args()
    loader = Loader('.', pprint=options.pprint)
    if len(args) > 0:
        template_name = args[0]
        template = loader.get_template(template_name)
        if options.code:
            printer = Printer()
            printer.visit(template.tree())
            print printer.src.getvalue()
        elif options.tokenize:
            for t in tokenizer(StringIO(template.source)):
                print t
        else:
            print template.render()
        if options.repeat > 0:
            now = datetime.datetime.now
            results = []
            for i in range(options.repeat):
                start = now()
                template.render()
                results.append(now() - start)
            print 'Total time (%d repeats): ' % options.repeat, reduce(lambda a,b: a+b, results)
            print 'Average:                 ', reduce(lambda a,b: a+b, results)/len(results)
    elif options.monitor:
        curdir = os.path.abspath(os.getcwd())
        try:
            render_templates(*all_files_by_mask('*.mint'), loader=loader)
            print 'Monitoring for file changes...'
            for changed_file in iter_changed():
                print 'Changes in file: ', changed_file, datetime.datetime.now().strftime('%H:%M:%S')
                render_templates(changed_file, loader=loader)
        except KeyboardInterrupt:
            pass
    else:
        print 'Try --help'
