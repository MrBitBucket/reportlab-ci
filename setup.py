#Copyright ReportLab Europe Ltd. 2000-2021
#see license.txt for license details
__version__='3.6.3'
import os, sys, glob, shutil, re, sysconfig, traceback, io, subprocess
from configparser import RawConfigParser
from urllib.parse import quote as urlquote
platform = sys.platform
pjoin = os.path.join
abspath = os.path.abspath
isfile = os.path.isfile
isdir = os.path.isdir
dirname = os.path.dirname
basename = os.path.basename
splitext = os.path.splitext
addrSize = 64 if sys.maxsize > 2**32 else 32
sysconfig_platform = sysconfig.get_platform()

INFOLINES=[]
def infoline(t,
        pfx='#####',
        add=True,
        ):
    bn = splitext(basename(sys.argv[0]))[0]
    ver = '.'.join(map(str,sys.version_info[:3]))
    s = '%s %s-python-%s-%s: %s' % (pfx, bn, ver, sysconfig_platform, t)
    print(s)
    if add: INFOLINES.append(s)

def showTraceback(s):
    buf = io.StringIO()
    print(s,file=buf)
    if verbose>2:
        traceback.print_exc(file=buf)
    for l in buf.getvalue().split('\n'):
        infoline(l,pfx='!!!!!',add=False)

def spCall(cmd,*args,**kwds):
    r = subprocess.call(
            cmd,
            stderr =subprocess.STDOUT,
            stdout = subprocess.DEVNULL if kwds.pop('dropOutput',False) else None,
            timeout = kwds.pop('timeout',3600),
            )
    if verbose>=3:
        infoline('%r --> %s' % (' '.join(cmd),r), pfx='!!!!!' if r else '#####', add=False)
    return r

def specialOption(n,ceq=False):
    v = 0
    while n in sys.argv:
        v += 1
        sys.argv.remove(n)
    if ceq:
        n += '='
        V = [_ for _ in sys.argv if _.startswith(n)]
        for _ in V: sys.argv.remove(_)
        if V:
            n = len(n)
            v = V[-1][n:]
    return v

#defaults for these options may be configured in local-setup.cfg
#[OPTIONS]
#no-download-t1-files=yes
#ignore-system-libart=yes
# if used on command line the config values are not used
dlt1 = not specialOption('--no-download-t1-files')
usla = specialOption('--use-system-libart')
mdbg = specialOption('--memory-debug')
verbose = specialOption('--verbose',ceq=True)
nullDivert = not verbose

if __name__=='__main__':
    pkgDir=dirname(sys.argv[0])
else:
    pkgDir=dirname(__file__)
if not pkgDir:
    pkgDir=os.getcwd()
elif not os.path.isabs(pkgDir):
    pkgDir=abspath(pkgDir)
try:
    os.chdir(pkgDir)
except:
    showTraceback('warning could not change directory to %r' % pkgDir)
daily=int(os.environ.get('RL_EXE_DAILY','0'))

try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension

def _packages_path(d):
    P = [_ for _ in sys.path if basename(_)==d]
    if P: return P[0]

package_path = _packages_path('dist-packages') or _packages_path('site-packages')
package_path = pjoin(package_path, 'reportlab')

def die(msg):
    raise ValueError(msg)

def make_libart_config(src):
    from struct import calcsize as sizeof
    L=["""/* Automatically generated by setup.py */
#ifndef _ART_CONFIG_H
#\tdefine _ART_CONFIG_H
#\tdefine ART_SIZEOF_CHAR %d
#\tdefine ART_SIZEOF_SHORT %d
#\tdefine ART_SIZEOF_INT %d
#\tdefine ART_SIZEOF_LONG %d""" % (sizeof('c'), sizeof('h'), sizeof('i'), sizeof('l'))
        ]
    aL = L.append

    if sizeof('c')==1:
        aL("typedef unsigned char art_u8;")
    else:
        die("sizeof(char) != 1")
    if sizeof('h')==2:
        aL("typedef unsigned short art_u16;")
    else:
        die("sizeof(short) != 2")

    if sizeof('i')==4:
        aL("typedef unsigned int art_u32;")
    elif sizeof('l')==4:
        aL("typedef unsigned long art_u32;")
    else:
        die("sizeof(int)!=4 and sizeof(long)!=4")
    aL('#endif\n')
    with open(pjoin(src,'art_config.h'),'w') as f:
        f.write('\n'.join(L))

def get_version():
    #determine Version
    if daily: return 'daily'

    #first try source
    FN = pjoin(pkgDir,'src','reportlab','__init__')
    try:
        for l in open(pjoin(FN+'.py'),'r').readlines():
            if l.startswith('Version'):
                D = {}
                exec(l.strip(),D)
                return D['Version']
    except:
        pass

    #don't have source, try import
    import imp
    for desc in ('.pyc', 'rb', 2), ('.pyo', 'rb', 2):
        try:
            fn = FN+desc[0]
            f = open(fn,desc[1])
            m = imp.load_module('reportlab',f,fn,desc)
            return m.Version
        except:
            pass
    raise ValueError('Cannot determine ReportLab Version')

class config:
    def __init__(self):
        try:
            self.parser = RawConfigParser()
            self.parser.read([pjoin(pkgDir,'setup.cfg'),pjoin(pkgDir,'local-setup.cfg')])
        except:
            self.parser = None

    def __call__(self,sect,name,default=None):
        try:
            return self.parser.get(sect,name)
        except:
            return default
config = config()

if dlt1:
    #not set on command line so try for config value
    dlt1 = not config('OPTIONS','no-download-t1-files','0').lower() in ('1','true','yes')
if not usla:
    #not set on command line so try for config value
    usla = config('OPTIONS','use-system-libart','0').lower() in ('1','true','yes')
if not mdbg:
    mdbg = config('OPTIONS','memory-debug','0').lower() in ('1','true','yes')

#this code from /FBot's PIL setup.py
def aDir(P, d, x=None):
    if d and isdir(d) and d not in P:
        if x is None:
            P.append(d)
        else:
            P.insert(x, d)

def findFile(root, wanted, followlinks=True):
    for p, _, F in os.walk(root,followlinks=followlinks):
        for fn in F:
            if fn==wanted:  
                return abspath(pjoin(p,fn))

def listFiles(root,followlinks=True,strJoin=None):
    R = [].append
    for p, _, F in os.walk(root,followlinks=followlinks):
        for fn in F:
            R(abspath(pjoin(p,fn)))
    R = R.__self__
    return strJoin.join(R) if strJoin else R

def freetypeVersion(fn,default='20'):
    with open(fn,'r') as _:
        text = _.read()
    pat = re.compile(r'^#define\s+FREETYPE_(?P<level>MAJOR|MINOR|PATCH)\s*(?P<value>\d*)\s*$',re.M)
    locmap=dict(MAJOR=0,MINOR=1,PATCH=2)
    loc = ['','','']
    for m in pat.finditer(text):
        loc[locmap[m.group('level')]] = m.group('value')
    loc = list(filter(None,loc))
    return '.'.join(loc) if loc else default

class inc_lib_dirs:
    def __call__(self,libname=None):
        L = config('FREETYPE_PATHS','lib')
        L = [L] if L else []
        I = config('FREETYPE_PATHS','inc')
        I = [I] if I else []
        if platform == "cygwin":
            aDir(L, os.path.join("/usr/lib", "python%s" % sys.version[:3], "config"))
        elif platform == "darwin":
            machine = sysconfig_platform.split('-')[-1]
            if machine=='arm64' or os.environ['ARCHFLAGS']=='-arch arm64':
                #print('!!!!! detected darwin arm64 build')
                #probably an M1
                target = pjoin(
                            ensureResourceStuff('m1stuff.tar.gz','m1stuff','tar',baseDir='/tmp/reportlab-cache'),
                            'm1stuff','opt','homebrew'
                            )
                _lib = pjoin(target,'lib')
                _inc = pjoin(target,'include','freetype2')
                strJoin='\n '
                print(f'!!!!! {target=}'
                print(f'!!!!! {_lib=} -->{strJoin}{listFiles(_lib,strJoin=strJoin)}')
                #print(f'!!!!! {_inc=} -->{strJoin}{listFiles(_inc,strJoin=strJoin)}')
                aDir(L, _lib)
                aDir(I, _inc)
                #print(f'!!!!! {L=} {I=}')
            elif machine=='x86_64':
                aDir(L,'/usr/local/lib')
                aDir(I, "/usr/local/include/freetype2")
            # attempt to make sure we pick freetype2 over other versions
            aDir(I, "/sw/include/freetype2")
            aDir(I, "/sw/lib/freetype2/include")
            # fink installation directories
            aDir(L, "/sw/lib")
            aDir(I, "/sw/include")
            # darwin ports installation directories
            aDir(L, "/opt/local/lib")
            aDir(I, "/opt/local/include")
        aDir(I, "/usr/local/include")
        aDir(L, "/usr/local/lib")
        aDir(I, "/usr/include")
        aDir(L, "/usr/lib")
        aDir(I, "/usr/include/freetype2")
        if addrSize==64:
            aDir(L, "/usr/lib/lib64")
            aDir(L, "/usr/lib/x86_64-linux-gnu")
        else:
            aDir(L, "/usr/lib/lib32")
        prefix = sysconfig.get_config_var("prefix")
        if prefix:
            aDir(L, pjoin(prefix, "lib"))
            aDir(I, pjoin(prefix, "include"))
        if libname:
            gsn = ''.join((('lib' if not libname.startswith('lib') else ''),libname,'*'))
            L = list(filter(lambda _: glob.glob(pjoin(_,gsn)),L))
        for d in I:
            mif = findFile(d,'ft2build.h')
            if mif:
                print(f'+++++ {d=} --> {mif=!r}')
                break
        else:
            mif = None
        if mif:
            d = dirname(mif)
            I = [dirname(d), d]
            ftv = freetypeVersion(findFile(d,'freetype.h'),'22')
        else:
            print('!!!!! cannot find ft2build.h')
            sys.exit(1)
        return ftv,I,L
inc_lib_dirs=inc_lib_dirs()

def getVersionFromCCode(fn):
    tag = re.search(r'^#define\s+VERSION\s+"([^"]*)"',open(fn,'r').read(),re.M)
    return tag and tag.group(1) or ''

class _rl_dir_info:
    def __init__(self,cn):
        self.cn=cn
    def __call__(self,dir):
        import stat
        fn = pjoin(dir,self.cn)
        try:
            return getVersionFromCCode(fn),os.stat(fn)[stat.ST_MTIME]
        except:
            return None

def _find_rl_ccode(dn='rl_accel',cn='_rl_accel.c'):
    '''locate where the accelerator code lives'''
    _ = []
    for x in [
            pjoin('src','rl_addons',dn),
            pjoin('rl_addons',dn),
            pjoin('..','rl_addons',dn),
            pjoin('..','..','rl_addons',dn),
            dn,
            pjoin('..',dn),
            pjoin('..','..',dn),
            ] \
            + glob.glob(pjoin(dn+'-*',dn))\
            + glob.glob(pjoin('..',dn+'-*',dn))\
            + glob.glob(pjoin('..','..',dn+'-*',dn))\
            :
        fn = pjoin(pkgDir,x,cn)
        if isfile(fn):
            _.append(x)
    if _:
        _ = list(filter(_rl_dir_info(cn),_))
        if len(_):
            _.sort(key=_rl_dir_info)
            _ = abspath(_[0])
            return _[_.index(os.sep.join(('','src','rl_addons')))+1:]

    return None


def BIGENDIAN(macname,value=None):
    'define a macro if bigendian'
    return sys.byteorder=='big' and [(macname,value)] or []

def pfxJoin(pfx,*N):
    R=[]
    for n in N:
        R.append(os.path.join(pfx,n))
    return R

reportlab_files= [
        'fonts/00readme.txt',
        'fonts/bitstream-vera-license.txt',
        'fonts/DarkGarden-changelog.txt',
        'fonts/DarkGarden-copying-gpl.txt',
        'fonts/DarkGarden-copying.txt',
        'fonts/DarkGarden-readme.txt',
        'fonts/DarkGarden.sfd',
        'fonts/DarkGardenMK.afm',
        'fonts/DarkGardenMK.pfb',
        'fonts/Vera.ttf',
        'fonts/VeraBd.ttf',
        'fonts/VeraBI.ttf',
        'fonts/VeraIt.ttf',
        'fonts/_abi____.pfb',
        'fonts/_ab_____.pfb',
        'fonts/_ai_____.pfb',
        'fonts/_a______.pfb',
        'fonts/cobo____.pfb',
        'fonts/cob_____.pfb',
        'fonts/com_____.pfb',
        'fonts/coo_____.pfb',
        'fonts/_ebi____.pfb',
        'fonts/_eb_____.pfb',
        'fonts/_ei_____.pfb',
        'fonts/_er_____.pfb',
        'fonts/sy______.pfb',
        'fonts/zd______.pfb',
        'fonts/zx______.pfb',
        'fonts/zy______.pfb',
        'fonts/callig15.pfb',
        'fonts/callig15.afm',
        'reportlab/graphics/barcode/README'
        'reportlab/graphics/barcode/TODO'
        'license.txt',
        ]

def url2data(url,returnRaw=False):
    import urllib.request as ureq
    remotehandle = ureq.urlopen(url)
    try:
        raw = remotehandle.read()
        return raw if returnRaw else io.BytesIO(raw)
    finally:
        remotehandle.close()

def ensureResourceStuff(
                ftpName='winstuff.zip',
                buildName='winstuff',
                extract='zip',
                baseDir=pjoin(pkgDir,'build'),
                ):
    url='https://www.reportlab.com/ftp/%s' % ftpName
    target=pjoin(baseDir,buildName)
    done = pjoin(target,'.done')
    if not isfile(done):
        if not isdir(target):
            os.makedirs(target)
            if extract=='zip':
                import zipfile
                zipfile.ZipFile(url2data(url), 'r').extractall(path=target)
            elif extract=='tar':
                import tarfile
                tarfile.open(fileobj=url2data(url), mode='r:gz').extractall(path=target)
            import time
            with open(done,'w') as _:
                _.write(time.strftime('%Y%m%dU%H%M%S\n',time.gmtime()))
    return target

def get_fonts(PACKAGE_DIR, reportlab_files):
    import zipfile
    rl_dir = PACKAGE_DIR['reportlab']
    if not [x for x in reportlab_files if not isfile(pjoin(rl_dir,x))]:
        xitmsg = "Standard T1 font curves already downloaded"
    elif not dlt1:
        xitmsg = "not downloading T1 font curve files"
    else:
        try:
            infoline("Downloading standard T1 font curves")
            zipdata = url2data("http://www.reportlab.com/ftp/pfbfer-20180109.zip")
            archive = zipfile.ZipFile(zipdata)
            dst = pjoin(rl_dir, 'fonts')

            for name in archive.namelist():
                if not name.endswith('/'):
                    with open(pjoin(dst, name), 'wb') as outfile:
                        outfile.write(archive.read(name))
            xitmsg = "Finished download of standard T1 font curves"
        except:
            xitmsg = "Failed to download standard T1 font curves"
    infoline(xitmsg)

def get_glyphlist_module(PACKAGE_DIR):
    try:
        lfn = pjoin("pdfbase","_glyphlist.py")
        fn = pjoin(PACKAGE_DIR['reportlab'],lfn)
        if isfile(fn):
            xitmsg = "The _glyphlist module already exists"
        else:
            text = url2data("https://raw.githubusercontent.com/adobe-type-tools/agl-aglfn/master/glyphlist.txt",True)
            comments = ['#see https://github.com/adobe-type-tools/agl-aglfn\n'].append
            G2U = [].append
            G2Us = [].append
            if not isinstance(text,str):
                text = text.decode('latin1')
            for line in text.split('\n'):
                line = line.strip()
                if not line: continue
                if line.startswith('#'):
                    comments(line+'\n')
                else:
                    gu = line.split(';')
                    if len(gu)==2:
                        v = gu[1].split()
                        if len(v)==1:
                            G2U('\t%r: 0x%s,\n' % (gu[0],gu[1]))
                        else:
                            G2Us('\t%r: (%s),\n' % (gu[0],','.join('0x%s'%u for u in v)))
                    else:
                        infoline('bad glyphlist line %r' % line, '!!!!!')
            with open(fn,'w') as f:
                f.write(''.join(comments.__self__))
                f.write('_glyphname2unicode = {\n')
                f.write(''.join(G2U.__self__))
                f.write('\t}\n')
                f.write('_glyphname2unicodes = {\n')
                f.write(''.join(G2Us.__self__))
                f.write('\t}\n')
            xitmsg = "Finished creation of _glyphlist.py"
    except:
        xitmsg = "Failed to download glyphlist.txt"
    infoline(xitmsg)

def canImport(pkg):
    ns = [pkg.find(_) for _ in '<>=' if _ in pkg]
    if ns: pkg =pkg[:min(ns)]
    ns = {}
    try:
        exec('import %s as M' % pkg,{},ns)
    except:
        if verbose>=2:
            showTraceback("can't import %s" % pkg)
    return 'M' in ns

def pipInstall(pkg, ixu=None):
    if canImport(pkg): return True
    i = ['-i%s' % ixu] if ixu else []
    r = spCall([sys.executable, '-mpip', 'install']+i+[pkg],dropOutput=verbose<3)
    return canImport(pkg)

def pipUninstall(pkg):
    spCall((sys.executable,'-mpip','-q','uninstall','-y', pkg), dropOutput=verbose<3)

def pipInstallGroups(pkgs, ixu=None):
    '''install groups of packages; if any of a group fail we backout the group'''
    for g in pkgs:
        I = []  #thse are the installed in this group
        for pkg in g.split():
            if pipInstall(pkg,ixu):
                I.append(pkg)
            else:
                print('!!!!! pip uninstalled %s' % repr(I)) 
                for pkg in I:
                    pipUninstall(pkg)
                I = []
                break
        if I:
            print('===== pip installed %s' % repr(I)) 

def vopt(opt):
    opt = '--%s=' % opt
    v = [_ for _ in sys.argv if _.startswith(opt)]
    for _ in v: sys.argv.remove(_)
    n = len(opt)
    return list(filter(None,[_[n:] for _ in v]))

class QUPStr(str):
    def __new__(cls,s,u,p):
        self = str.__new__(cls,s)
        self.u = u
        self.p = p
        return self

def qup(url, pat=re.compile(r'(?P<scheme>https?://)(?P<up>[^@]*)(?P<rest>@.*)$')):
    '''urlquote the user name and password'''
    m = pat.match(url)
    if m:
        u, p = m.group('up').split(':',1)
        url = "%s%s:%s%s" % (m.group('scheme'),urlquote(u),urlquote(p),m.group('rest'))
    else:
        u = p = ''
    return QUPStr(url,u,p)

def performPipInstalls():
    pip_installs = vopt('pip-install')
    pipInstallGroups(pip_installs)
    rl_pip_installs = vopt('rl-pip-install')
    if rl_pip_installs:
        rl_ixu = vopt('rl-index-url')
        if len(rl_ixu)==1:
            pipInstallGroups(rl_pip_installs,qup(rl_ixu[0]))
        else:
            raise ValueError('rl-pip-install requires exactly 1 --rl-index-url not %d' % len(rl_ixu))

def showEnv():
    action = -1 if specialOption('--show-env-only') else 1 if specialOption('--show-env') else 0
    if not action: return
    print('+++++ setup.py environment')
    print('+++++ sys.version = %s' % sys.version.replace('\n',''))
    import platform
    for k in sorted((_ for _ in dir(platform) if not _.startswith('_'))):
        try:
            v = getattr(platform,k)
            if isinstance(v,(str,list,tuple,bool)):
                v = repr(v)
            if callable(v) and v.__module__=='platform':
                v = repr(v())
            else:
                continue
        except:
            v = '?????'
        print('+++++ platform.%s = %s' % (k,v))
    print('--------------------------')
    for k, v in sorted(os.environ.items()):
        print('+++++ environ[%s] = %r' % (k,v))
    print('--------------------------')
    if action<0:
        sys.exit(0)

def main():
    showEnv()
    performPipInstalls()
    #test to see if we've a special command
    if 'test' in sys.argv \
        or 'tests' in sys.argv \
        or 'tests-postinstall' in sys.argv \
        or 'tests-preinstall' in sys.argv:
        verboseTests = specialOption('--verbose-tests')
        if len(sys.argv)!=2:
            raise ValueError('tests commands may only be used alone sys.argv[1:]=%s' % repr(sys.argv[1:]))
        cmd = sys.argv[-1]
        PYTHONPATH = [pkgDir] if cmd!='test' else []
        if cmd=='tests-preinstall':
            PYTHONPATH.insert(0,pjoin(pkgDir,'src'))
        if PYTHONPATH: os.environ['PYTHONPATH']=os.pathsep.join(PYTHONPATH)
        os.chdir(pjoin(pkgDir,'tests'))
        cli = [sys.executable, 'runAll.py']
        if cmd=='tests-postinstall':
            cli.append('--post-install')
        if verboseTests:
            cli.append('--verbosity=2')
        r = spCall(cli)
        sys.exit(('!!!!! runAll.py --> %s should exit with error !!!!!' % r) if r else r)
    elif 'null-cmd' in sys.argv or 'null-command' in sys.argv:
        sys.exit(0)

    debug_compile_args = []
    debug_link_args = []
    debug_macros = []
    debug = int(os.environ.get('RL_DEBUG','0'))
    if debug:
        if sys.platform == 'win32':
            debug_compile_args=['/Zi']
            debug_link_args=['/DEBUG']
        if debug>1:
            debug_macros.extend([('RL_DEBUG',debug), ('ROBIN_DEBUG',None)])
    if mdbg:
        debug_macros.extend([('MEMORY_DEBUG',None)])

    SPECIAL_PACKAGE_DATA = {}
    RL_ACCEL = _find_rl_ccode('rl_accel','_rl_accel.c')
    LIBRARIES=[]
    EXT_MODULES = []

    if not RL_ACCEL:
        infoline( '===================================================')
        infoline( 'not attempting build of the _rl_accel extension')
        infoline( '===================================================')
    else:
        infoline( '================================================')
        infoline( 'Attempting build of _rl_accel')
        infoline( 'extensions from %r'%RL_ACCEL)
        infoline( '================================================')
        EXT_MODULES += [
                    Extension( 'reportlab.lib._rl_accel',
                                [pjoin(RL_ACCEL,'_rl_accel.c')],
                                include_dirs=[],
                            define_macros=[]+debug_macros,
                            library_dirs=[],
                            libraries=[], # libraries to link against
                            extra_compile_args=debug_compile_args,
                            extra_link_args=debug_link_args,
                            ),
                        ]
    RENDERPM = _find_rl_ccode('renderPM','_renderPM.c')
    if not RENDERPM:
        infoline( '===================================================')
        infoline( 'not attempting build of _renderPM')
        infoline( '===================================================')
    else:
        infoline( '===================================================')
        infoline( 'Attempting build of _renderPM')
        infoline( 'extensions from %r'%RENDERPM)
        infoline( '===================================================')
        GT1_DIR=pjoin(RENDERPM,'gt1')

        if not usla:
            LIBART_INC=None #don't use system libart
        else:
            #check for an installed libart
            LIBART_INC = list(sorted(glob.glob('/usr/include/libart-*/libart_lgpl/libart-features.h')))
        if LIBART_INC:
            def installed_libart_version(fn):
                for l in open(fn, 'r').readlines():
                    if l.startswith('#define LIBART_VERSION'):
                        v = l[:-1].split(' ')[-1]
                        return v
                return '"0.0.0"'
            LIBART_INC = LIBART_INC[-1]
            LIBART_VERSION = installed_libart_version(LIBART_INC)
            LIBART_INC = os.path.dirname(LIBART_INC)
            LIBART_SOURCES=[]
            LIBART_LIB = ['art_lgpl_2']
            infoline('will use installed libart %s' % LIBART_VERSION.replace('"',''))
        else:
            LIBART_DIR = LIBART_INC = pjoin(RENDERPM,'libart_lgpl')
            LIBART_LIB = []
            make_libart_config(LIBART_DIR)
            LIBART_SOURCES=[
                    pjoin(LIBART_DIR,'art_vpath_bpath.c'),
                    pjoin(LIBART_DIR,'art_rgb_pixbuf_affine.c'),
                    pjoin(LIBART_DIR,'art_rgb_svp.c'),
                    pjoin(LIBART_DIR,'art_svp.c'),
                    pjoin(LIBART_DIR,'art_svp_vpath.c'),
                    pjoin(LIBART_DIR,'art_svp_vpath_stroke.c'),
                    pjoin(LIBART_DIR,'art_svp_ops.c'),
                    pjoin(LIBART_DIR,'art_svp_wind.c'),
                    pjoin(LIBART_DIR,'art_vpath.c'),
                    pjoin(LIBART_DIR,'art_vpath_dash.c'),
                    pjoin(LIBART_DIR,'art_affine.c'),
                    pjoin(LIBART_DIR,'art_rect.c'),
                    pjoin(LIBART_DIR,'art_rgb_affine.c'),
                    pjoin(LIBART_DIR,'art_rgb_affine_private.c'),
                    pjoin(LIBART_DIR,'art_rgb.c'),
                    pjoin(LIBART_DIR,'art_rgb_rgba_affine.c'),
                    pjoin(LIBART_DIR,'art_svp_intersect.c'),
                    pjoin(LIBART_DIR,'art_svp_render_aa.c'),
                    pjoin(LIBART_DIR,'art_misc.c'),
                    ]
            def libart_version():
                pat0 = re.compile(r'^\s*LIBART_(MAJOR|MINOR|MICRO)_VERSION\s*=\s*(\d+)')
                pat1 = re.compile(r'^\s*m4_define\s*\(\s*\[\s*libart_(major|minor|micro)_version\s*\]\s*,\s*\[(\d+)\]\s*\)')
                def check_match(l):
                    for p in (pat0, pat1):
                        m = p.match(l)
                        if m: return m
                K = ('major','minor','micro')
                D = {}
                for l in open(pjoin(LIBART_DIR,'configure.in'),'r').readlines():
                    m = check_match(l)
                    if m:
                        D[m.group(1).lower()] = m.group(2)
                        if len(D)==3: break
                return '.'.join(map(lambda k,D=D: D.get(k,'?'),K))
            LIBART_VERSION = libart_version()
            infoline('will use package libart %s' % LIBART_VERSION.replace('"',''))

        SOURCES=[pjoin(RENDERPM,'_renderPM.c'),
                    pjoin(GT1_DIR,'gt1-parset1.c'),
                    pjoin(GT1_DIR,'gt1-dict.c'),
                    pjoin(GT1_DIR,'gt1-namecontext.c'),
                    pjoin(GT1_DIR,'gt1-region.c'),
                    ]+LIBART_SOURCES

        if platform=='win32':
            target = ensureResourceStuff()
            FT_LIB = pjoin(target,'libs','amd64' if addrSize==64 else 'x86','freetype.lib')
            if not isfile(FT_LIB):
                infoline('freetype lib %r not found' % FT_LIB, pfx='!!!!')
                FT_LIB=[]
            if FT_LIB:
                FT_INC_DIR = pjoin(target,'include')
                if not isfile(pjoin(FT_INC_DIR,'ft2build.h')):
                    FT_INC_DIR = pjoin(FT_INC_DIR,'freetype2')
                    if not isfile(pjoin(FT_INC_DIR,'ft2build.h')):
                        infoline('freetype2 include folder %r not found' % FT_INC_DIR, pfx='!!!!!')
                        FT_LIB=FT_LIB_DIR=FT_INC_DIR=FT_MACROS=[]
                FT_MACROS = [('RENDERPM_FT',None)]
                FT_LIB_DIR = [dirname(FT_LIB)]
                FT_INC_DIR = [FT_INC_DIR]
                FT_LIB_PATH = FT_LIB
                FT_LIB = [splitext(basename(FT_LIB))[0]]
                if isdir(FT_INC_DIR[0]):
                    infoline('installing with freetype %r' % FT_LIB_PATH)
            else:
                FT_LIB=FT_LIB_DIR=FT_INC_DIR=FT_MACROS=[]
        else:
            ftv, I, L = inc_lib_dirs('freetype')
            FT_LIB=['freetype']
            FT_LIB_DIR=L
            FT_INC_DIR=I
            FT_MACROS = [('RENDERPM_FT',None)]
            infoline('installing with freetype version %s' % ftv)
            infoline('FT_LIB_DIR=%r FT_INC_DIR=%r' % (FT_LIB_DIR,FT_INC_DIR))
        if not FT_LIB:
            infoline('# installing without freetype no ttf, sorry!')
            infoline('# You need to install a static library version of the freetype2 software')
            infoline('# If you need truetype support in renderPM')
            infoline('# You may need to edit setup.cfg (win32)')
            infoline('# or edit this file to access the library if it is installed')

        EXT_MODULES +=  [Extension( 'reportlab.graphics._renderPM',
                                        SOURCES,
                                        include_dirs=[RENDERPM,LIBART_INC,GT1_DIR]+FT_INC_DIR,
                                        define_macros=FT_MACROS+[('LIBART_COMPILATION',None)]+debug_macros+[('LIBART_VERSION',LIBART_VERSION)],
                                        library_dirs=[]+FT_LIB_DIR,

                                        # libraries to link against
                                        libraries=FT_LIB+LIBART_LIB,
                                        extra_compile_args=debug_compile_args,
                                        extra_link_args=debug_link_args,
                                        ),
                            ]
        infoline('################################################')

    #copy some special case files into place so package_data will treat them properly
    PACKAGE_DIR = {'':'src','reportlab': pjoin('src','reportlab')}
    for fn,dst in SPECIAL_PACKAGE_DATA.items():
        shutil.copyfile(fn,pjoin(PACKAGE_DIR['reportlab'],dst))
        reportlab_files.append(dst)
    get_fonts(PACKAGE_DIR, reportlab_files)
    get_glyphlist_module(PACKAGE_DIR)
    try:
        setup(
            name="reportlab",
            version=get_version(),
            license="BSD license (see license.txt for details), Copyright (c) 2000-2018, ReportLab Inc.",
            description="The Reportlab Toolkit",
            long_description="""The ReportLab Toolkit. An Open Source Python library for generating PDFs and graphics.""",

            author="Andy Robinson, Robin Becker, the ReportLab team and the community",
            author_email="reportlab-users@lists2.reportlab.com",
            url="http://www.reportlab.com/",
            packages=[
                    'reportlab',
                    'reportlab.graphics.charts',
                    'reportlab.graphics.samples',
                    'reportlab.graphics.widgets',
                    'reportlab.graphics.barcode',
                    'reportlab.graphics',
                    'reportlab.lib',
                    'reportlab.pdfbase',
                    'reportlab.pdfgen',
                    'reportlab.platypus',
                    ],
            package_dir = PACKAGE_DIR,
            package_data = {'reportlab': reportlab_files},
            ext_modules =   EXT_MODULES,
            classifiers = [
                'Development Status :: 5 - Production/Stable',
                'Intended Audience :: Developers',
                'License :: OSI Approved :: BSD License',
                'Topic :: Printing',
                'Topic :: Text Processing :: Markup',
                'Programming Language :: Python :: 3',
                'Programming Language :: Python :: 3.6',
                'Programming Language :: Python :: 3.7',
                'Programming Language :: Python :: 3.8',
                'Programming Language :: Python :: 3.9',
                'Programming Language :: Python :: 3.10',
                'Programming Language :: Python :: 3.11',
                ],
            
            #this probably only works for setuptools, but distutils seems to ignore it
            install_requires=['pillow>=4.0.0'],
            python_requires='>=3.6, <4',
            extras_require={
                'RLPYCAIRO': ['rlPyCairo>=0.0.5'],
                },
            )
        print()
        print('########## SUMMARY INFO #########')
        print('\n'.join(INFOLINES))
    finally:
        for dst in SPECIAL_PACKAGE_DATA.values():
            os.remove(pjoin(PACKAGE_DIR['reportlab'],dst))
            reportlab_files.remove(dst)

if __name__=='__main__':
    main()
