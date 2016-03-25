import logging
import os
import re
import sublime
import sublime_plugin
import sys

sys.path.insert(0, os.path.dirname(__file__))
from SyntaxMappings import *


PLUGIN_NAME = 'AutoSetSyntax'
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(name)s: [%(levelname)s] %(message)s"

settings = None
workingScopeRegex = None
syntaxMappings = None
loggingStreamHandler = None
logger = None


def plugin_unloaded():
    global settings, loggingStreamHandler, logger

    settings.clear_on_change('syntax_mapping')
    settings.clear_on_change('working_scope')
    logger.removeHandler(loggingStreamHandler)


def plugin_loaded():
    global settings, workingScopeRegex, syntaxMappings, loggingStreamHandler, logger

    # create logger stream handler
    loggingStreamHandler = logging.StreamHandler()
    loggingStreamHandler.setFormatter(logging.Formatter(LOG_FORMAT))
    # config logger
    logger = logging.getLogger(PLUGIN_NAME)
    logger.setLevel(LOG_LEVEL)
    logger.addHandler(loggingStreamHandler)

    settings = sublime.load_settings(PLUGIN_NAME+'.sublime-settings')

    syntaxMappings = SyntaxMappings(settings=settings, logger=logger)
    compileWorkingScope()

    # rebuilt syntax mappings if there is an user settings update
    settings.add_on_change('syntax_mapping', syntaxMappings.rebuildSyntaxMappings)
    settings.add_on_change('working_scope', compileWorkingScope)


def compileWorkingScope():
    """ compile workingScope into regex object to get better speed """

    global settings, workingScopeRegex, logger

    workingScope = settings.get('working_scope')
    try:
        workingScopeRegex = re.compile(workingScope)
    except:
        errorMessage = 'regex compilation failed in user settings "{0}": {1}'.format('working_scope', workingScope)
        logger.error(errorMessage)
        sublime.error_message(errorMessage)
        workingScopeRegex = None


class AutoSetNewFileSyntax(sublime_plugin.EventListener):
    global settings, workingScopeRegex, syntaxMappings

    def on_activated_async(self, view):
        """ called when a view gains input focus """

        if (
            self.isEventListenerEnabled('on_activated_async') and
            self.isOnWorkingScope(view)
        ):
            view.run_command('auto_set_syntax')

    def on_clone_async(self, view):
        """ called when a view is cloned from an existing one """

        if (
            self.isEventListenerEnabled('on_clone_async') and
            self.isOnWorkingScope(view)
        ):
            view.run_command('auto_set_syntax')

    def on_load_async(self, view):
        """ called when the file is finished loading """

        if (
            self.isEventListenerEnabled('on_load_async') and
            self.isOnWorkingScope(view)
        ):
            view.run_command('auto_set_syntax')

    def on_modified_async(self, view):
        """ called after changes have been made to a view """

        if (
            self.isEventListenerEnabled('on_modified_async') and
            self.isOnlyOneCursor(view) and
            self.isFirstCursorNearBeginning(view) and
            self.isOnWorkingScope(view)
        ):
            view.run_command('auto_set_syntax')

    def on_new_async(self, view):
        """ called when a new buffer is created """

        if (
            self.isEventListenerEnabled('on_new_async') and
            self.isOnWorkingScope(view)
        ):
            view.run_command('auto_set_syntax')

    def on_post_text_command(self, view, command_name, args):
        """ called after a text command has been executed """

        if (
            self.isOnWorkingScope(view) and
            (
                self.isEventListenerEnabled('on_post_paste') and
                (
                    command_name == 'patse' or
                    command_name == 'paste_and_indent'
                )
            )
        ):
            view.run_command('auto_set_syntax')

    def on_pre_save_async(self, view):
        """ called just before a view is saved """

        if (
            self.isEventListenerEnabled('on_pre_save_async') and
            self.isOnWorkingScope(view)
        ):
            view.run_command('auto_set_syntax')

    def isEventListenerEnabled(self, event):
        """ check a event listener is enabled """

        try:
            return settings.get('event_listeners', None)[event]
        except:
            logger.warning('"{0}" is not set in user settings (assumed true)'.format('event_listeners -> '+event))
            return True

    def isOnlyOneCursor(self, view):
        """ check there is only one cursor """

        return len(view.sel()) == 1

    def isFirstCursorNearBeginning(self, view):
        """ check the cursor is at first few lines """

        return view.rowcol(view.sel()[0].a)[0] < 2

    def isOnWorkingScope(self, view):
        """ check the scope of the first line is matched by working_scope """

        if (
            workingScopeRegex is None or
            workingScopeRegex.search(view.scope_name(0)) is None
        ):
            return False
        return True


class autoSetSyntaxCommand(sublime_plugin.TextCommand):
    global settings, syntaxMappings

    def run(self, edit):
        """ match the first line and set the corresponding syntax """

        firstLine = self.getPartialFirstLine()
        for syntaxMapping in syntaxMappings.value():
            syntaxFile, firstLineMatchRegexes = syntaxMapping
            for firstLineMatchRegex in firstLineMatchRegexes:
                if firstLineMatchRegex.search(firstLine) is not None:
                    self.view.set_syntax_file(syntaxFile)
                    return

    def getPartialFirstLine(self):
        """ get the (partial) first line """

        region = self.view.line(0)
        firstLineLengthMax = settings.get('first_line_length_max')
        if firstLineLengthMax >= 0:
            # if the first line is longer than the max line length,
            # then we use the max line length
            region = sublime.Region(0, min(region.end(), firstLineLengthMax))
        return self.view.substr(region)
