"""Collect every href/src from the site's HTML; check internal ones against files; list external ones."""
import os, re, sys, json
from urllib.parse import urljoin, urlparse, unquote
from html.parser import HTMLParser
ROOT = sys.argv[1]
class P(HTMLParser):
    def __init__(s): super().__init__(); s.links=[]; s.ids=set()
    def handle_starttag(s, tag, a):
        a=dict(a)
        if 'id' in a: s.ids.add(a['id'])
        if tag=='a' and 'name' in a: s.ids.add(a['name'])
        for k in ('href','src'):
            v=a.get(k)
            if v and tag in ('a','img','script','link','iframe','source','video','audio'):
                if tag=='link' and a.get('rel') in ('preconnect','dns-prefetch'): continue
                s.links.append((tag,v.strip(),s.getpos()[0]))
pages={}
for d,_,fs in os.walk(ROOT):
    if '/.git' in d or '/node_modules' in d: continue
    for f in fs:
        if f.endswith('.html'):
            p=os.path.join(d,f); rel='/'+os.path.relpath(p,ROOT)
            x=P(); x.feed(open(p,encoding='utf-8',errors='replace').read()); pages[rel]=x
internal_bad=[]; external={}
def exists(path):
    fp=os.path.join(ROOT, unquote(path).lstrip('/'))
    if os.path.isfile(fp): return True
    if os.path.isdir(fp) and os.path.isfile(os.path.join(fp,'index.html')): return True
    if os.path.isfile(fp+'.html'): return True
    return False
for rel,x in pages.items():
    base='https://brooksgroves.com'+rel
    for tag,v,line in x.links:
        if v.startswith(('mailto:','tel:','javascript:','data:','#')) or '${' in v or '{{' in v or "'+" in v or '"+' in v:
            if v.startswith('#') and len(v)>1 and v[1:] not in x.ids and not v.startswith('#/'):
                internal_bad.append((rel,line,v,'missing anchor'))
            continue
        u=urljoin(base,v); pu=urlparse(u)
        if pu.netloc in ('brooksgroves.com','www.brooksgroves.com'):
            if exists(pu.path): continue
            # path not in this repo: may be another repo's Pages site (brooksgroves.com/<repo>/)
            external.setdefault(u.split('#')[0],[]).append(f"{rel}:{line}")
        elif pu.scheme in ('http','https'):
            external.setdefault(u.split('#')[0],[]).append(f"{rel}:{line}")
json.dump(external, open(sys.argv[2],'w'), indent=0)
for r in internal_bad: print('BAD', *r)
print(len(pages),'pages;',len(external),'distinct external/other-repo URLs')
