import unittest
import pprint
import os

from zope.testing import doctest, cleanup
from zope.component import provideUtility, provideAdapter, adapts
from zope.interface import classProvides, implements

from collective.transmogrifier.interfaces import ISectionBlueprint, ISection
from collective.transmogrifier.tests import tearDown
from collective.transmogrifier.sections.tests import sectionsSetUp
from collective.transmogrifier.sections.tests import SampleSource

from Products.Five import zcml

import quintagroup.transmogrifier
from quintagroup.transmogrifier.xslt import stylesheet_registry

class DataPrinter(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.printkey = [i.strip() for i in options['print'].splitlines() if i.strip()]
        if 'prettyprint' in options:
            self.pprint = pprint.PrettyPrinter().pprint

    def __iter__(self):
        for item in self.previous:
            if self.printkey:
                data = item
                for i in self.printkey:
                    if i in data:
                        data = data[i]
                    else:
                        data = None
                        break
                if data is not None:
                    if hasattr(self, 'pprint'):
                        self.pprint(data)
                    else:
                        print data
            yield item

ctSectionsSetup = sectionsSetUp
def sectionsSetUp(test):
    ctSectionsSetup(test)
    import Products.Five
    import Products.GenericSetup
    import zope.annotation
    zcml.load_config('meta.zcml', Products.Five)
    zcml.load_config('meta.zcml', Products.GenericSetup)
    zcml.load_config('configure.zcml', zope.annotation)
    zcml.load_config('configure.zcml', quintagroup.transmogrifier)

    from Products.CMFCore import utils
    def getToolByName(context, tool_id):
        return context
    utils.getToolByName = getToolByName

    import Acquisition
    def aq_base(obj):
        return obj
    Acquisition.aq_base = aq_base

    provideUtility(DataPrinter,
        name=u'quintagroup.transmogrifier.tests.dataprinter')

def siteWalkerSetUp(test):
    sectionsSetUp(test)

    from Products.CMFCore.interfaces import IFolderish
    from Products.Archetypes.interfaces import IBaseFolder

    class MockContent(object):
        path = ()

        def getPhysicalPath(self):
            return self.path

        def getPortalTypeName(self):
            return self.__class__.__name__

    class Document(MockContent):
        pass

    class Folder(MockContent, dict):
        implements(IBaseFolder)

        contentItems = dict.items
        contentValues = dict.values

    class MockPortal(MockContent, dict):
        implements(IFolderish)

        contentItems = dict.items
        contentValues = dict.values

    portal = MockPortal()

    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

    portal.path = ('', 'plone')
    portal['document1'] = Document()
    portal['document1'].path = ('', 'plone', 'document1')
    portal['folder1'] = Folder()
    portal['folder1'].path = ('', 'plone', 'folder1')
    portal['folder1']['document2'] = Document()
    portal['folder1']['document2'].path = ('', 'plone', 'folder1', 'document2')
    portal['folder1']['folder2'] = Folder()
    portal['folder1']['folder2'].path = ('', 'plone', 'folder1', 'folder2')
    portal['document3'] = Document()
    portal['document3'].path = ('', 'plone', 'document3')

def manifestSetUp(test):
    sectionsSetUp(test)

    root = dict(
        _path='',
        _entries=(
            ('news', 'Folder'),
            ('events', 'Folder'),
            ('front-page', 'Document')
        )
    )

    news = dict(
        _path='news',
        _entries=(
            ('aggregator', 'Topic'),
            ('not-existing', 'SomeType')
        )
    )

    aggregator = dict(
        _path='news/aggregator',
    )

    events = dict(
        _path='events'
    )

    front_page = dict(
        _path='front-page',
    )

    members = dict(
        _path='Memebers'
    )

    class ManifestSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(ManifestSource, self).__init__(*args, **kw)
            self.sample = (root, dict(), news, aggregator, events, front_page, members)

    provideUtility(ManifestSource,
        name=u'quintagroup.transmogrifier.tests.manifestsource')

def marshallSetUp(test):
    sectionsSetUp(test)

    from Products.Archetypes.interfaces import IBaseObject

    class MockBase(object):
        def checkCreationFlag(self):
            return True

        def unmarkCreationFlag(self):
            pass

        def at_post_create_script(self):
            pass

        def at_post_edit_script(self):
            pass

        indexed = ()
        def indexObject(self):
            self.indexed += (self._last_path,)

    class MockCriterion(MockBase):
        implements(IBaseObject)
        _last_path = None
        indexed = ()
        def indexObject(self):
            self.indexed += (self._last_path,)

    class MockPortal(MockBase):
        implements(IBaseObject)

        criterion = MockCriterion()

        _last_path = None
        def unrestrictedTraverse(self, path, default):
            if path[0] == '/':
                return default # path is absolute
            if isinstance(path, unicode):
                return default
            if path == 'not/existing/bar':
                return default
            if path == 'topic/criterion':
                self._last_path = path
                self.criterion._last_path = path
                return self.criterion
            if path.endswith('/notatcontent'):
                return object()
            self._last_path = path
            return self

        def getId(self):
            return "plone"

        indexed = ()
        def indexObject(self):
            self.indexed += (self._last_path,)

        marshalled = ()
        def marshall(self, instance, **kwargs):
            self.marshalled += ((self._last_path, kwargs.get('atns_exclude')),)
            # Marshall often fails to export topic criteria
            if isinstance(instance, MockCriterion):
                return None, None, None
            else:
                return None, None, "marshalled"

        demarshalled = ()
        def demarshall(self, instance, data):
            # we don't need to test Marshall product, only check if we call it's components
            self.demarshalled += (self._last_path,)

    portal = MockPortal()
    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

    from Products.Marshall import registry
    def getComponent(name):
        return portal
    registry.getComponent = getComponent

    class MarshallSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(MarshallSource, self).__init__(*args, **kw)
            self.sample = (
                dict(),
                dict(_path='spam/eggs/foo', _excluded_fields=('file', 'image')),
                dict(_path='topic/criterion'),
                dict(_path='not/existing/bar'),
                dict(_path='spam/eggs/notatcontent', 
                     _files=dict(marshall=dict(data='xml', name='.marshall.xml'))),
            )
    provideUtility(MarshallSource,
        name=u'quintagroup.transmogrifier.tests.marshallsource')

def propertyManagerSetUp(test):
    sectionsSetUp(test)

    from OFS.interfaces import IPropertyManager

    class MockPortal(object):
        implements(IPropertyManager)

        _properties = (
            {'id':'title', 'type': 'string', 'mode': 'w'},
            {'id':'description', 'type': 'string', 'mode': 'w'},
            {'id':'encoding', 'type': 'string', 'mode': 'w'},
            {'id':'author', 'type': 'string', 'mode': 'w'}
        )

        _last_path = None
        def unrestrictedTraverse(self, path, default):
            if path[0] == '/':
                return default # path is absolute
            if isinstance(path, unicode):
                return default
            if path == 'not/existing/bar':
                return default
            if path.endswith('/notatcontent'):
                return object()
            self._last_path = path
            return self

        def _propertyMap(self):
            return self._properties

        def getProperty(self, id, d=None):
            return 'value'

        def propdict(self):
            d={}
            for p in self._properties:
                d[p['id']]=p
            return d

        updated = ()
        def _updateProperty(self, id, value):
            self.updated += ((self._last_path, id, value.strip()))

    portal = MockPortal()
    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

    class PropertyManagerSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(PropertyManagerSource, self).__init__(*args, **kw)
            self.sample = (
                dict(),
                dict(_path='not/existing/bar'),
                dict(_path='spam/eggs/notatcontent'),
                dict(_path='spam/eggs/foo', _excluded_properties=('encoding',)),
            )

    provideUtility(PropertyManagerSource,
        name=u'quintagroup.transmogrifier.tests.propertymanagersource')

def commentsSetUp(test):
    sectionsSetUp(test)

    class MockDiscussionItem(object):
        creator = 'creator'
        modified = 'date'

        def __init__(self, reply, text=""):
            self.in_reply_to = reply
            self.text = text

        def __of__(self, container):
            return self

        def getMetadataHeaders(self):
            return []

        def setMetadata(self, headers):
            pass

        def Creator(self):
            return self.creator

        def addCreator(self, creator):
            self.creator = creator

        def ModificationDate(self):
            return self.modified

        def setModificationDate(self, date):
            self.modified = date

        def setFormat(self, format):
            pass

        def _edit(self, text=None):
            self.text = text

        def indexObject(self):
            pass

        def __repr__(self):
            return "<DicussionItem %s %s %s %s>" % (
                self.Creator(),
                self.ModificationDate(),
                self.in_reply_to,
                self.text
                )

    from Products.CMFDefault import DiscussionItem
    DiscussionItem.DiscussionItem = MockDiscussionItem

    class MockPortal(object):
        _discussion = {
            '1': MockDiscussionItem(None, 'comment to content'),
            '2': MockDiscussionItem('1', 'reply to first comment'),
            '3': MockDiscussionItem(None, 'other comment to content')
        }
        _container = {}

        @property
        def talkback(self):
            return self

        def objectItems(self):
            l = self._discussion.items()
            l.sort(key=lambda x: int(x[0]))
            return l

        def unrestrictedTraverse(self, path, default):
            if path[0] == '/':
                return default # path is absolute
            if isinstance(path, unicode):
                return default
            if path == 'not/existing/bar':
                return default
            if path.endswith('/notdiscussable'):
                return object()
            return self

        def getDiscussionFor(self, obj):
            return self

    portal = MockPortal()
    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

    class CommentsSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(CommentsSource, self).__init__(*args, **kw)
            self.sample = (
                dict(),
                dict(_path='not/existing/bar'),
                dict(_path='spam/eggs/notdiscussable'),
                dict(_path='spam/eggs/foo'),
            )

    provideUtility(CommentsSource,
        name=u'quintagroup.transmogrifier.tests.commentssource')


def dataCorrectorSetUp(test):
    sectionsSetUp(test)

    class MockPortal(object):
        def unrestrictedTraverse(self, path, default):
            if path[0] == '/':
                return default # path is absolute
            if isinstance(path, unicode):
                return default
            if path == 'not/existing/bar':
                return default
            if path.endswith('/notadaptable'):
                return object()
            return self

    portal = MockPortal()
    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

    from quintagroup.transmogrifier.interfaces import IExportDataCorrector, \
        IImportDataCorrector

    class MockExportAdapter(object):
        implements(IExportDataCorrector)
        adapts(MockPortal)
        def __init__(self, context):
            self.context = context

        def __call__(self, data):
            return "modified export data"

    provideAdapter(MockExportAdapter, name="marshall")

    class MockImportAdapter(object):
        implements(IImportDataCorrector)
        adapts(MockPortal)
        def __init__(self, context):
            self.context = context

        def __call__(self, data):
            return "modified import data"

    provideAdapter(MockImportAdapter, name="manifest")

    class DataCorrectorSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(DataCorrectorSource, self).__init__(*args, **kw)
            self.sample = (
                dict(),
                dict(_files=dict(marshall="item hasn't path")),
                dict(_path='spam/eggs/foo'),
                dict(_path='not/existing/bar'),
                dict(_path='spam/eggs/notadaptable', _files=dict(marshall="object isn't adaptable")),
                dict(_path='spam/eggs/foo',
                     _files=dict(marshall='marshall data', unchanged='this must be unchanged')),
                dict(_path='spam/eggs/foo',
                     _files=dict(manifest='manifest data', unchanged='this must be unchanged')),
            )

    provideUtility(DataCorrectorSource,
        name=u'quintagroup.transmogrifier.tests.datacorrectorsource')

def writerSetUp(test):
    sectionsSetUp(test)

    class MockExportContext(object):
        def __init__( self, *args, **kwargs):
            self.args = args
            for k, v in kwargs.items():
                setattr(self, k, v)
            self._wrote = []

        def __getitem__(self, name):
            return getattr(self, name, None)

        def __contains__(self, name):
            return hasattr(self, name)

        def writeDataFile(self, filename, text, content_type, subdir=None):
            filename = '%s/%s' % (subdir, filename)
            self._wrote.append((filename, text, content_type))

        def __repr__(self):
            s = " ".join(["%s=%s" % (k,v) for k,v in self.__dict__.items()])
            return "<%s %s>" % (self.__class__.__name__, s)


    from Products.GenericSetup import context

    context.DirectoryExportContext = type('Directory', (MockExportContext,), {})
    context.TarballExportContext = type('Tarball', (MockExportContext,), {})
    context.SnapshotExportContext = type('Snapshot', (MockExportContext,), {})

    class WriterSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(WriterSource, self).__init__(*args, **kw)
            self.sample = (
                dict(_path='spam/eggs/foo'),
                dict(_files=dict(mock=dict(name='.first.xml', data='some data'))),
                dict(_path='spam/eggs/foo',
                     _files=dict(mock=dict(name='.first.xml', data='some data'),
                                 other=dict(name='.second.xml', data='other data'))),
                dict(_path='other/path',
                     _files=dict(mock=dict(name='.third.xml', data='some data')))
            )

    provideUtility(WriterSource,
        name=u'quintagroup.transmogrifier.tests.writersource')

    class SingleItemSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(SingleItemSource, self).__init__(*args, **kw)
            self.sample = (
                dict(_path='', _files={}),
            )

    provideUtility(SingleItemSource,
        name=u"quintagroup.transmogrifier.tests.singleitemsource")

def readerSetUp(test):
    sectionsSetUp(test)

    class MockImportContext(object):

        _dirs = [
            'structure',
            'structure/news', 'structure/news/recent',
            'structure/pages', 'structure/pages/front-page',
        ]
        _files = [
            'structure/.properties.xml',
            'structure/other.file',
            'structure/news/.objects.xml',
            'structure/pages/.objects.xml',
            'structure/pages/front-page/.marshall.xml',
            'structure/pages/front-page/.comments.xml',
        ]

        def __init__( self, *args, **kwargs):
            self.args = args
            for k, v in kwargs.items():
                setattr(self, k, v)

        def __repr__(self):
            s = " ".join(["%s=%s" % (k,v) for k,v in self.__dict__.items()])
            return "<%s %s>" % (self.__class__.__name__, s)

        def readDataFile(self, filename, subdir=None):
            return 'some data'

        def isDirectory(self, path):
            return path == '' or path in self._dirs

        def listDirectory(self, path):
            all_names = self._dirs + self._files
            if path:
                pfx_len = len(path)+1
            else:
                pfx_len = 0
            names = []
            for name in all_names:
                if name == path:
                    continue
                if not name.startswith(path):
                    continue
                name = name[pfx_len:]
                if '/' in name:
                    continue
                names.append(name)
            return names

    from Products.GenericSetup import context

    context.DirectoryImportContext = type('Directory', (MockImportContext,),
        {'listDirectory': lambda self, path: []})
    context.TarballImportContext = type('Tarball', (MockImportContext,), {})
    context.SnapshotImportContext = type('Snapshot', (MockImportContext,),
        {'listDirectory': lambda self, path: []})

def substitutionSetUp(test):
    sectionsSetUp(test)

    class SubstitutionSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(SubstitutionSource, self).__init__(*args, **kw)
            self.sample = (
                {},
                {'_type': 'Blog'},
                {'_type': 'PloneFormMailer'},
                {'_type': 'Document'},
            )

    provideUtility(SubstitutionSource,
        name=u'quintagroup.transmogrifier.tests.substitutionsource')

class MetaDirectivesTests(unittest.TestCase):
    def setUp(self):
        zcml.load_config('meta.zcml', quintagroup.transmogrifier)

    def tearDown(self):
        stylesheet_registry.clear()
        cleanup.cleanUp()

    def testEmptyZCML(self):
        zcml.load_string('''\
<configure xmlns:transmogrifier="http://namespaces.plone.org/transmogrifier">
</configure>''')
        self.assertEqual(stylesheet_registry.listStylesheetNames(), ())

    def testConfigZCML(self):
        zcml.load_string('''\
<configure
    xmlns:transmogrifier="http://namespaces.plone.org/transmogrifier">
<transmogrifier:stylesheet
    source="marshall"
    from="Blog"
    to="Weblog"
    file="blog.xsl"
    />
</configure>''')
        self.assertEqual(stylesheet_registry.listStylesheetNames(),
                         (u'marshall:Blog:Weblog',))
        path = os.path.split(quintagroup.transmogrifier.__file__)[0]
        self.assertEqual(
            stylesheet_registry.getStylesheet('marshall', 'Blog', 'Weblog'),
            dict(from_=u'Blog',
                 to=u'Weblog',
                 file=os.path.join(path, 'blog.xsl'))
        )

    def testMultipleZCML(self):
        zcml.load_string('''\
<configure
    xmlns:transmogrifier="http://namespaces.plone.org/transmogrifier">
<transmogrifier:stylesheet
    source="marshall"
    from="Blog"
    to="Weblog"
    file="blog.xsl"
    />
<transmogrifier:stylesheet
    source="propertymanager"
    from="BlogEntry"
    to="WeblogEntry"
    file="blogentry.xsl"
    />
</configure>''')
        self.assertEqual(stylesheet_registry.listStylesheetNames(),
                         (u'marshall:Blog:Weblog', u'propertymanager:BlogEntry:WeblogEntry'))

def xsltSetUp(test):
    sectionsSetUp(test)

    class XSLTSource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(XSLTSource, self).__init__(*args, **kw)
            self.sample = (
                {},
                {'_type': 'Weblog'},
                {'_old_type': 'Blog'},
                {'_old_type': 'Blog',
                 '_type': 'Weblog',
                 '_files': {'manifest': {'data': 'xml', 'name': 'manifest.xml'}}},
                {'_old_type': 'Blog',
                 '_type': 'Weblog',
                 '_files': {'marshall': {'data': 'xml', 'name': 'marshall.xml'}}},
            )

    provideUtility(XSLTSource,
        name=u'quintagroup.transmogrifier.tests.xsltsource')

    from quintagroup.transmogrifier.xslt import XSLTSection, stylesheet_registry

    XSLTSection.applyTransformations = lambda self, xml, xslt: 'transformed xml'
    test.globs['stylesheet_registry'] = stylesheet_registry

def binarySetUp(test):
    sectionsSetUp(test)

    from Products.Archetypes.interfaces import IBaseObject

    class MockPortal(object):
        implements(IBaseObject)

        _last_path = None
        def unrestrictedTraverse(self, path, default):
            if path[0] == '/':
                return default # path is absolute
            if isinstance(path, unicode):
                return default
            if path == 'not/existing/bar':
                return default
            if path.endswith('/notatcontent'):
                return object()
            self._last_path = path
            return self

        fields = ['id', 'title', 'file', 'image']

        def Schema(self):
            return dict.fromkeys(self.fields)

        def isBinary(self, field):
            return field in ('file',) #, 'image')

        def getField(self, field):
            return self

        def getBaseUnit(self, obj):
            return self

        def getFilename(self):
            return "archive.tar.gz"

        def getContentType(self):
            return 'application/x-tar'

        def getRaw(self):
            return "binary data"

        def getMutator(self, obj):
            return self

        updated = ()
        def __call__(self, data, filename=None, mimetype=None):
            self.updated += (filename, mimetype, data)

    portal = MockPortal()
    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

    class BinarySource(SampleSource):
        classProvides(ISectionBlueprint)
        implements(ISection)

        def __init__(self, *args, **kw):
            super(BinarySource, self).__init__(*args, **kw)
            self.sample = (
                dict(),
                dict(_path='not/existing/bar'),
                dict(_path='spam/eggs/notatcontent'),
                dict(_path='spam/eggs/foo'),
            )

    provideUtility(BinarySource,
        name=u'quintagroup.transmogrifier.tests.binarysource')

from DateTime import DateTime

def catalogSourceSetUp(test):
    sectionsSetUp(test)

    class MockContent(dict):
        def __init__(self, **kw):
            self.update(kw)
            self['id'] = self.getId

        def getPath(self):
            return self['path']

        @property
        def getId(self):
            path = self.getPath()
            return path.rsplit('/', 1)[-1]

        @property
        def Type(self):
            return self['portal_type']

        @property
        def is_folderish(self):
            return self['portal_type'] == 'Folder' and True or False

    class MockPortal(dict):

        content = ()
        def __call__(self, **kw):
            res = []
            for obj in self.content:
                matched = True
                for index, query in kw.items():
                    if index not in obj:
                        matched = False
                        break
                    if matched and index == 'modified':
                        if isinstance(query, dict):
                            value = query['query']
                            range_ = query['range']
                            if range_ == 'min' and DateTime(obj[index]) >= DateTime(value):
                                matched = True
                            elif range_ == 'max' and DateTime(obj[index]) <= DateTime(value):
                                matched = True
                            else:
                                matched = False
                        else:
                            if DateTime(obj[index]) == DateTime(query):
                                matched = True
                            else:
                                matched = False
                    elif matched and index == 'path':
                        if obj[index].startswith(query):
                            matched = True
                        else:
                            matched = False
                    elif matched:
                        if obj[index] == query:
                            matched = True
                        else:
                            matched = False
                if matched:
                    res.append(obj)

            return res

    portal = MockPortal()
    doc1 = MockContent(path='/plone/document1', portal_type='Document',
        modified='2008-11-01T12:00:00Z')
    folder1 = MockContent(path='/plone/folder1', portal_type='Folder',
        modified='2008-11-01T12:00:00Z')
    doc2 = MockContent(path='/plone/folder1/document2', portal_type='Document',
        modified='2008-11-02T12:00:00Z')
    doc3 = MockContent(path='/plone/folder1/document3', portal_type='Document',
        modified='2008-11-02T12:00:00Z')
    folder2 = MockContent(path='/plone/folder2', portal_type='Folder',
        modified='2008-11-02T12:00:00Z')
    doc4 = MockContent(path='/plone/folder2/document4', portal_type='Document',
        modified='2008-11-01T12:00:00Z')
    comment = MockContent(path='/plone/folder2/document4/talkback/1234567890', portal_type='Discussion Item',
        modified='2008-11-02T12:00:00Z')
    # items are sorted on their modification date
    portal.content = (doc1, folder1, folder2, doc2, doc3, doc4, comment)

    test.globs['plone'] = portal
    test.globs['transmogrifier'].context = test.globs['plone']

def test_suite():
    import sys
    suite = unittest.findTestCases(sys.modules[__name__])
    suite.addTests((
        doctest.DocFileSuite(
            'sitewalker.txt',
            setUp=siteWalkerSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'manifest.txt',
            setUp=manifestSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'marshall.txt',
            setUp=marshallSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'propertymanager.txt',
            setUp=propertyManagerSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'comments.txt',
            setUp=commentsSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'datacorrector.txt',
            setUp=dataCorrectorSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'writer.txt',
            setUp=writerSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'reader.txt',
            setUp=readerSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'substitution.txt',
            setUp=substitutionSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'xslt.txt',
            setUp=xsltSetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'binary.txt',
            setUp=binarySetUp, tearDown=tearDown),
        doctest.DocFileSuite(
            'catalogsource.txt',
            setUp=catalogSourceSetUp, tearDown=tearDown),
    ))
    return suite
