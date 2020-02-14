#!/usr/bin/python3
# -*- coding: utf-8 -*-

import bibtexparser
import sys
import requests
from box import SBox
from functools import partial
from contracts import contract
import copy
from urllib.parse import unquote
import re
import argparse
from collections import defaultdict
import os
from pathlib import Path
import nwalign3 as nw
import types
import signal
import maya
import textwrap
from pylatexenc.latex2text import LatexNodes2Text


def handler(signum, frame):
    eprint('CTRL+C was pressed.'    )
    sys.exit(1)

signal.signal(signal.SIGINT, handler)

parser = argparse.ArgumentParser(description='BiBTeX fixer.')
parser.add_argument('--fix-all', '-F', action='store_true')
parser.add_argument('--fix-enclosing', action='store_true')
parser.add_argument('--input', '-i', default=sys.stdin, action='store')
parser.add_argument('--output', '-o', default=sys.stdout, action='store')
parser.add_argument('--no-color', '-C', dest='color', default=True, action='store_false')
parser.add_argument('--color', '-c', dest='color', default=True, action='store_true')
args = parser.parse_args()

if args.fix_all:
    args.fix_enclosing = True

errors, warnings, fixes = 0,0,0

warning_rules = []
error_rules = []
fixing_rules = []


if args.color:
    from colorama import init, Fore, Back, Style
    init()

    def red(s):
        return f'{Fore.RED}{s}{Fore.RESET}'

    def yellow(s):
        return f'{Fore.YELLOW}{s}{Fore.RESET}'

    def green(s):
        return f'{Fore.GREEN}{s}{Fore.RESET}'

    def cyan(s):
        return f'{Fore.CYAN}{s}{Fore.RESET}'

else:
    red = green = yellow = cyan = lambda x:x


def eprint(*arglist, **kwargs):
    print(*arglist, file=sys.stderr, **kwargs)


def doi2bib(doi):
    """
    Return a bibTeX string of metadata for a given DOI.
    """
    url = "http://dx.doi.org/" + doi
    headers = {"accept": "application/x-bibtex"}
    r = requests.get(url, headers = headers)
    if not r.ok:
        eprint(r.status_code)
        sys.exit(1)
    return r.text


def rule(func,rule_type):
    if rule_type[0] == 'E':
        idx = len(error_rules)
        error_rules.append(partial(func,idx))
    elif rule_type[0]== 'W':
        idx = len(warning_rules)
        warning_rules.append(partial(func,idx))
    elif rule_type[0]== 'F':
        idx = len(fixing_rules)
        fixing_rules.append(partial(func,idx))
    return func

def missing_entry(etype,key,msg,idx,entry):
    skip_list = (('issn','arxivid'),('url','doi'),('doi','isbn'), ('doi','arxivid'))
    if entry['ENTRYTYPE']==etype:
        keys = key.split('|')
        for key in keys:
            if key in entry:
                return None,None,None
            for skip_key, condition in skip_list:
                if key == skip_key and condition in entry:
                    return None,None,None
        return key,f'{idx:02d}', msg
    return None,None,None


def modifications(a0,b0):
    if a0.find('\n') >= 0 :
        return Fore.RED+a0+Fore.RESET,Fore.GREEN+b0+Fore.RESET,b0
    if len(a0)==0:
        N=len(b0)
        A=" "*N
        B=green(b0)
        C=b0
        return A,B,C

    a,b= nw.global_align(a0,b0)
    if len(a)!=len(b):
        print(a0)
        print(a)
        print(b0)
        print(b)
        assert False

    A,B,C="","",""

    for i in range(len(a)):
        if a[i]==b[i]:
            A+=Fore.RESET+a[i]
            B+=Fore.RESET+a[i]
            C+=Fore.RESET+a[i]
        elif a[i]=='-':
                A+=' '
                B+=Fore.GREEN+b[i]
                C+=Fore.RESET+b[i]
        else:
                A+=Fore.RESET+a[i]
                B+=Fore.RED+a[i]
                C+=Fore.RESET+' '
    A+=Fore.RESET
    B+=Fore.RESET
    C+=Fore.RESET
    return A,B,C


def enclosing_fix(text):
    text = text.strip().strip('{').strip('}')
    parts = text.split()
    result = []
    for idx,part in enumerate(parts):
        part = part.strip('{').strip('}')
        if part[1:] != part[1:].lower():
            result.append( '{'+part+'}')
        else:
            result.append( part)
    return " ".join(result)

def enclosing(idx,entry):
    global fixes
    for key in ['title','abstract']:
        if key in entry:
            v = entry[key].strip().replace('}{','} {').replace('} {','}  {')

            if v.startswith('{') and v.endswith('}'):
                fixed = enclosing_fix(entry[key])
                if fixed != v:
                    if fixed.find('\n')>=0 or v.find('\n')>=0:
                        a,b,c = v, fixed, fixed
                    else:
                        a,b,c = modifications(v,fixed)
                    if args.fix_enclosing:
                        fixes += 1
                        entry[key] = fixed
                        result = f'possibly misused protection  in "{yellow(key)}"'
                        # ~ result +='\n input: ' +a
                        # ~ result +='\n diff.: ' +b
                        # ~ result +=f'\n {Fore.GREEN}fixed{Fore.RESET}: ' +c
                        return key, f"{idx:02}", result
                    else:
                        result = f'possibly misused protection  in "{yellow(key)}" which could be fixed as:'
                        # ~ result +='\n  input   : ' +a
                        # ~ result +='\n  diff.   : ' +b
                        # ~ result +=f'\n  {Fore.CYAN}proposed{Fore.RESET}: ' +c
                        return key, f"{idx:02}", result

    return None,None,None

def find_fields(entry, doi):
    try:
        bibstring = doi2bib(doi)
        bib = bibtexparser.loads(bibstring)
        online_entry = bib.entries[0]
    except:
        eprint('invalid doi')
        return None
    updated = SBox(copy.deepcopy(entry),default_box=True)
    online_entry.update(updated)
    return online_entry

def fix_paragraphs(text):
    text = re.sub(r'(\s(?P<pattern>BACKGROUND|Background))',r'\n\n\g<pattern>',text)
    text = re.sub(r'(\s(?P<pattern>METHODS|Methods))',r'\n\n\g<pattern>',text)
    text = re.sub(r'(\s(?P<pattern>CONCLUSION|Conclusion))',r'\n\n\g<pattern>',text)
    text = re.sub(r'(\s(?P<pattern>RESULTS|Results))',r'\n\n\g<pattern>',text)
    return text

def fix_wrap(idx, entry, indent = 20):
    wrapper = textwrap.TextWrapper()
    wrapper.width=70
    wrapper.break_long_words = False
    wrapper.break_on_hyphen = False
    indent_text = ' '*indent

    for key in entry.keys():
        value = entry[key]
        if key.lower() in ['abstract','title', 'booktitle'] and len(value)>wrapper.width+15:
            result = f"\n{indent_text}".join(wrapper.wrap(entry[key]))
            if key == 'abstract':
                result = fix_paragraphs(result)
            entry[key] = result
            yield key, f"{idx:02}", result
        if key.lower() in ['author', 'editor']:
            names = value.strip().split(' and ')
            N = max(map(len,map(str.strip,names)))

            padded_names = []
            for name in names:
                k = N - len(name)
                padded_names.append(name + (' '*k))
            result = f'  and\n{indent_text}'.join(padded_names).strip()
            entry[key] = result
            yield key, f"{idx:02}", result


def latex2text(src):
    text = src.replace('\textless','<')
    text = src.replace('\textgreater','>')
    text = LatexNodes2Text().latex_to_text(text).replace('%',r'\%')
    return text

def fix_fields(idx,entry):
    for key in list(entry.keys()):
        if key not in ['ENTRYTYPE','ID','month']:
            entry[key] = entry[key].strip('{').strip('}')
            entry[key] = latex2text(entry[key])
    if 'doi' in entry and args.fix_all:
        updated = find_fields(entry,entry['doi'])
        if updated is not None:
            for key in list(updated.keys()):
                a,b = entry.get(key,""), updated[key]
                if key == 'url':
                    b = unquote(b)
                if a!=b:
                    if key == 'url':
                        if b.find('doi.org'):
                            result = f"key ({yellow(key)}) is a DOI derivative, therefore it is removed.\n"
                            result += f"       deleted: {red(b)}"
                            if 'url' in entry: entry.pop('url')
                            yield key, f"{idx:02}", result
                            return
                    entry[key] = b
                    result = f" missing key ({yellow(key)}) found online"
                    yield key, f"{idx:02}", result

def fix_pages(idx,entry):
    if 'pages' in entry:
        pages = entry.pages
        pages = pages.strip('{').strip('}')
        pages.replace('-','--')
        pages.replace('--','x')
        entry.pages = pages
    return None,None,None

def fix_month(idx,entry):
    if 'month' in entry:
        month = str(entry.month)
        month = month.strip('{').strip('}')
        try:
            month = int(month)
        except:
            month = maya.parse(month).month
        entry.month = str(month)
    return None,None,None

# mandatory fields
for bibtype, fields in (
    ('article',('author','title','journal','year')),
    ('booklet',('title','author')),
    ('book',('author|editor', 'title', 'publisher','year')),
    ('inbook',('author|editor', 'title', 'chapter|pages', 'publisher', 'year')),
    ('incollection',('author', 'title', 'booktitle', 'publisher', 'year')),
    ('inproceedings',('author', 'title', 'booktitle', 'year')),
    ('masterthesis',('author','title', 'school', 'year')),
    ('phdthesis',('author','title', 'school', 'year')),
    ('proceedings',('title', 'year')),
    ('techreport',('author','title', 'year','institution')),
    ('unpublished',('author','title', 'note')),
    ):
    for key in fields:
        idx = len(error_rules)
        rule(partial(missing_entry,bibtype,key,f'missing mandatory field: {red(key.replace("|"," or "))}'),f'E{idx:02d}')

# recommended fields
for t, fields in (
    ('article',('doi','issn')),
    ('booklet',( 'howpublished', 'year', 'doi', 'url')),
    ('ibbook',( 'volume', 'number', 'series','type','address','edition', 'month')),
    ('incollection',( 'editor', 'chapter', 'pages', 'volume|number', 'series','type','address','edition', 'month')),
    ('inproceedings',( 'editor', 'volume|number', 'series','pages','address','edition', 'month', 'publisher', 'note', 'organization')),
    ('manual',('author','organization','address', 'edition', 'month', 'year', 'note', 'url')),
    ('masterthesis',('type','adddress', 'month', 'note')),
    ('phdthesis',('type','adddress', 'month', 'note')),
    ('misc',('type','adddress', 'month', 'note', 'url')),
    ('proceedings',('editor','volume|number', 'series', 'address', 'publisher','note','month','organization')),
    ('techreport',('type','number', 'month', 'address', 'note')),
    ('unpublished',('month', 'year')),
    ):
    for f in fields:
        idx = len(warning_rules)
        rule(partial(missing_entry,t,f,f'missing recommended field "{yellow(f)}"'),f'W{idx:02d}')



# ~ idx = len(warning_rules)
# ~ rule(check_year,f'missing recommended field "{yellow(f)}"'),f'W{idx:02d}')



idx = len(fixing_rules)
rule(enclosing,f'W{idx}')
idx = len(fixing_rules)
rule(fix_fields,f'F{idx}')
idx = len(fixing_rules)
rule(fix_pages,f'F{idx}')
idx = len(fixing_rules)
rule(fix_month,f'F{idx}')

idx = len(fixing_rules)
rule(fix_wrap,f'F{idx}')


def check_entry(entry, nr):
    original = copy.deepcopy(entry)
    e_messages = defaultdict(set)
    w_messages = defaultdict(set)
    f_messages = defaultdict(set)
    ID = entry.ID

    if 'title' in entry:
        if len(entry['title'])>80:
            title = entry['title'][0:80]+ ' ...'
        else:
            title = entry['title']
    else:
        title = red('unknown title')

    for msgs,ruleset in ((e_messages, error_rules),(w_messages, warning_rules), (f_messages, fixing_rules),):
        for idx,r in enumerate(ruleset):
            rentry = r(entry)
            if not isinstance(rentry, tuple):
                for key, rule, msg in r(entry):
                    if rule:
                        msgs[key].add( (rule, msg))

            else:
                key, rule, msg = rentry
                if rule:
                    msgs[key].add( (rule, msg))


    if len(e_messages)+len(w_messages)+len(f_messages)>0:
        eprint(f'\n#{nr:<3} In {cyan(entry["ID"])} ({entry["ENTRYTYPE"]}): {title}')

    keys = set(list(e_messages.keys()) + list(w_messages.keys()) + list(f_messages.keys()))

    e,w,f = 0,0,0

    for key in keys:
        cnt = 0
        for rule, msg in e_messages[key]:
            eprint(f' {Fore.RED}E{rule}{Fore.RESET}:  {msg}')
            e+=1
            cnt+=1

        for rule, msg in w_messages[key]:
            eprint(f' {Fore.YELLOW}W{rule}{Fore.RESET}:  {msg}')
            w+=1
            cnt+=1

        for rule, msg in f_messages[key]:
            eprint(f' {Fore.CYAN}F{rule}{Fore.RESET}:  {msg}')
            f+=1
            cnt+=1

        orig = original.get(key,'')
        value = entry.get(key,None)
        if key in entry and orig != value:
            if key != 'url' and value.find('\n')==-1:
                a,b,c = modifications(orig,value)
                eprint(f'  original: {Fore.RED}{a}{Fore.RESET}')
                eprint(f'  changes:  {Fore.RESET}{b}{Fore.RESET}')
                eprint(f'  fixed:    {Fore.RESET}{c}{Fore.RESET}')
            else:
                eprint(f'  original: {Fore.RED}{orig}{Fore.RESET}')
                eprint(f'  fixed:    {Fore.GREEN}{value}{Fore.RESET}')

        if cnt>0: eprint()
    return e,w,f


if isinstance(args.input, str):
    print(Path(args.input))
    with open(Path(args.input),"rt") as f:
            bibstrings = f.read()
else:
    bibstrings = args.input.read()

bib = bibtexparser.loads(bibstrings)
errors = 0

bib.entries = list(map(SBox,bib.entries))

writer = bibtexparser.bwriter.BibTexWriter()
writer.add_trailing_comma = True
writer.display_order = ('title','author','booktitle','editor','abstract','journal','issn','year','volume','month','number','pages','publisher','address','doi','pubmedid','url','notes')
writer.ordering_entries_by = None
writer.align_values=10


for nr, entry in enumerate(bib.entries):
    e,w,f = check_entry(entry, nr)
    errors += e
    warnings += w
    fixes += f
    # ~ if nr>3:break

if args.color:
    eprint(f'Summary:   {Fore.RED}errors: {errors} {Fore.YELLOW}warnings: {warnings} {Fore.GREEN} fixes: {fixes} {Fore.RESET}')
else:
    eprint(f'Summary:   errors: {errors}    warnings: {warnings}    fixes: {fixes}')
if isinstance(args.output, str):
    with open(args.output,"wt") as f:
        f.write(bibtexparser.dumps(bib,writer))
else:
    args.output.write(bibtexparser.dumps(bib,writer))


if errors > 0:
    sys.exit(1)

# ~ for line in lines:
    # ~ line = line.replace("  ", " ")
    # ~ doi, ref, comment = map(string.strip, (line + "  ").split(" ", 2))
    # ~ doi = doi.replace("https://dx.doi.org/", "")
    # ~ doi = doi.replace("http://dx.doi.org/", "")
    # ~ doi = doi.strip("/{}, =")
    # ~ if doi in processed:
        # ~ continue
    # ~ result = doi2bib(doi).strip()
    # ~ if result.startswith("@"):
        # ~ x = bibtexparser.loads(result)
        # ~ x.entries[0] = sanitize_dict(x.entries[0])
        # ~ db = x.entries[0]
        # ~ db['id'] = db['id'].replace("_", "")
        # ~ if ref != "":
            # ~ db['id'] = unicode("%s" % ref)
        # ~ if comment == "" and u'title' in db:
            # ~ comment = db['title']
        # ~ ID = (db['id'])
        # ~ if ID in refs:
            # ~ print("DUPLICATED KEY!!! [%s]" % ID, file=sys.stderr)
            # ~ sys.exit(1)
        # ~ refs[ID] = doi
        # ~ if update:
            # ~ print("%30s  %15s       %s" % (doi, ID, comment))
        # ~ else:
            # ~ serialized = bibtexparser.dumps(x)
            # ~ print(serialized)
        # ~ processed[doi] = True

    # ~ elif result.startswith("<"):
        # ~ processed[doi] = None
        # ~ print("DOI not found: %s " % line, file=sys.stderr)
