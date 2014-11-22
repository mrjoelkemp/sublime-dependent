import sublime, sublime_plugin
import subprocess
import threading
import os
import re
import time
from .preconditions import *
from .thread_progress import ThreadProgress
from .node_dependents import get_dependents
from .project_settings import get_project_settings
from .show_error import show_error

class DependentsCommand(sublime_plugin.WindowCommand):
    def run(self, modifier=''):
        base_path = self.window.folders()[0] + '/'

        settings = get_project_settings(base_path)

        self.window.root = settings['root']
        self.window.config = settings['config']
        self.window.sass_root = settings['sass_root']

        if not self.window.root and not self.window.sass_root:
            show_error('Please set the "root" or "sass_root" in \nPreferences -> Package Settings -> Dependents -> Settings - User')
            return

        self.view = self.window.active_view()
        self.view.filename = self.view.file_name()
        # The part of the path before the root
        self.view.path = base_path
        self.view.modifier = modifier
        self.view.isSassFile = isSassFile(self.view.filename)

        # All subsequent actions will be about the sass_root so just
        # switch the root to reduce the redundant checking if we should
        # use root or sass_root
        if self.view.isSassFile:
            self.window.root = self.window.sass_root

        if not met(self.view.path):
            return

        thread = DependentsThread(self.window, self.view)
        thread.start();

        ThreadProgress(thread, 'Finding dependents', '')

class DependentsThread(threading.Thread):
    """
    A thread to prevent the determination of the dependents from freezing the UI
    """
    def __init__(self, window, view):
        self.window = window
        self.view = view
        threading.Thread.__init__(self)

    def run(self):
        """
        Finds the dependents of the current file and jumps to that file or shows a panel of dependent files
        """
        start_time = time.time()

        self.dependents = self.trim_paths(self.get_dependents())

        print('Dependents: Elapsed - %s seconds' % (time.time() - start_time))

        if self.view.modifier and self.view.modifier == 'OPEN_ALL':
            for dep in self.dependents:
                self.open_file(dep)
            return

        if len(self.dependents) == 1:
            self.open_file(self.dependents[0])
        else:
            sublime.set_timeout(self.show_quick_panel, 10)

    def get_dependents(self):
        """
        Asks the node tool for the dependents of the current module
        """
        args = {
            'filename': self.view.filename,
            'root': self.view.path + self.window.root
        }

        if self.window.config:
            args['config'] = self.view.path + self.window.config

        dependents = get_dependents(args)
        print('Dependents found:')
        print('\n'.join(dependents))
        return dependents

    def trim_paths(self, files):
        """
        Returns the filepaths for each file minus the root and its trailing slash
        """
        trimmed = []

        for f in files:
            if f:
                try:
                    filename = f[f.index(self.window.root) + len(self.window.root) + 1:]
                except:
                    print('Didn\'t have root in path: ', f)
                    filename = f

                trimmed.append(filename)

        return trimmed

    def show_quick_panel(self):
        if not self.dependents:
            show_error('\nCan\'t find any file that depends on this file')
            return

        self.window.show_quick_panel(self.dependents, self.on_done)

    def on_done(self, picked):
        if picked == -1:
            return

        dependent = self.dependents[picked]
        self.open_file(dependent)

    def open_file(self, dependent):
        # We removed the root originally when populating the dependents list
        filename = self.view.path + self.window.root + '/' + dependent

        if not os.path.isfile(filename):
            cant_find_file()
            return

        def open():
            self.window.open_file(filename)

        sublime.set_timeout(open, 10)

def cant_find_file():
    show_error('Can\'t find that file')

def isSassFile(filename):
    """
    Whether or not the given filename is a Sass file
    """

    extension = os.path.splitext(filename)[1]
    print('ext: ', extension)
    print('filename: ', filename)

    return extension == '.scss' or extension == '.sass'
