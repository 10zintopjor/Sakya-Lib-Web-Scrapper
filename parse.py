from uuid import uuid4
from openpecha.core.pecha import OpenPechaFS
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum,PechaMetaData
from openpecha.core.annotation import Page, Span
from openpecha.core.ids import get_pecha_id
from bs4 import BeautifulSoup
from datetime import datetime
import requests
import re
import re
import logging
from openpecha import github_utils,config

input_source = "https://sakyalibrary.com"
pechas_catalog = ''
err_log = ''
text_api = 'http://sakyalibrary.com/library/BookPage?bookId={book_id}&pgNo={page_no}'
main_api = 'http://sakyalibrary.com/library/Book/{book_id}'

def make_request(url):
    response = requests.get(url)
    return response


def get_text(book_id):
    base_text = {}
    response = make_request(main_api.format(book_id=book_id))
    page = BeautifulSoup(response.content,'html.parser')
    base_text = get_into_page(book_id,1,base_text)
    return base_text


def get_into_page(book_id,page_no,base_text):
    response = make_request(text_api.format(book_id=book_id,page_no=page_no))
    base_text.update({page_no:response.text.strip("\n")})
    if has_next_page(book_id,page_no+1):
        _ = get_into_page(book_id,page_no+1,base_text)
    return base_text
    

def has_next_page(book_id,page_no):
    status = ""
    response = make_request(text_api.format(book_id=book_id,page_no=page_no))
    if response.status_code != 200:
        status = False
    else:
        status = True     
    return status


def extract_book_id(url):
    book_id = re.match(".*Book/(.*)",url).group(1)
    return book_id


def create_opf(opf_path,base_text,base_id):
    opf = OpenPechaFS(opf_path=opf_path)
    layers = {f"{base_id}": {LayerEnum.pagination: get_layers(base_text)}}
    bases = {f"{base_id}":get_base_text(base_text)}
    opf.layers = layers
    opf.base = bases
    opf.save_base()
    opf.save_layers()


def get_base_text(base_text):
    text = ""
    for elem in base_text:
        text+=base_text[elem]+"\n\n"
    return text


def get_layers(base_text):
    page_annotations= {}
    char_walker = 0
    for page_no in base_text:
        page_annotation,char_walker = get_page_annotation(page_no,base_text[page_no],char_walker)
        page_annotations.update(page_annotation)

    pagination_layer = Layer(
        annotation_type=LayerEnum.pagination,annotations=page_annotations
    )    
    return pagination_layer


def get_page_annotation(page_no,text,char_walker):
    page_start = char_walker
    page_end = char_walker +len(text)
    page_annotation = {
        uuid4().hex:Page(span=Span(start=page_start,end=page_end),metadata={"page_no":page_no})
    }

    return page_annotation,page_end+2


def write_meta(opf_path,col):
    instance_meta = PechaMetaData(
        initial_creation_type=InitialCreationEnum.input,
        created_at=datetime.now(),
        last_modified_at=datetime.now(),
        source_metadata={
            "title":col['title'],
            "parent":col["parent"],
            "source":input_source,
            "bases":get_source_meta(col['vol'])
        })
    opf = OpenPechaFS(opf_path=opf_path)
    opf._meta = instance_meta
    opf.save_meta()


def get_source_meta(bases):
    meta= {}
    order =1
    for base_id in bases:
        title,author = bases[base_id]
        meta.update({base_id:{
            "title":title,
            "author":author,
            "base_file": f"{base_id}.txt",
            "order":order
        }})
        order+=1
    return meta    


def get_collections(url):
    response = make_request(url)
    page = BeautifulSoup(response.content,'html.parser')
    collections = page.select_one("div#tab_collections")
    divs = collections.findChildren("div",recursive=False)
    for div in divs:
        yield from get_links(div)


def get_links(div):
    main_title = div.select_one("h4.panel-title a span").text
    sub_titles = div.select("div.panel.panel-default.tab_topic")
    for sub_title in sub_titles:
        dict = {}
        vols =[]
        link_tags = sub_title.find_next_sibling('div').select("div.file-text.row")
        has_more = sub_title.find_next_sibling('div').select_one("div.book-more a")
        if has_more:
            link = has_more["href"]
            link_tags = get_more_links(link,sub_title.text.strip())
        for link_tag in link_tags:
            title = link_tag.select_one('div').text.strip()
            link = link_tag.select_one('a')['href']
            author = link_tag.select_one('div.file-text-author.col-sm-2.col-xs-4').text.strip()
            vols.append({"title":title,"link":link,"author":author})
        dict.update({"title":sub_title.text.strip(),"parent":main_title,"vol":vols}) 
        yield dict
    

def get_more_links(link,main_title):
    response = make_request("http://sakyalibrary.com/"+link)
    page = BeautifulSoup(response.content,'html.parser')
    titles = page.select("div.panel.panel-default") 
    for title in titles:
        in_title = title.select_one("h4.panel-title a span").text.strip()
        if in_title == main_title:
            link_tags = title.select("div.panel-body div.file-text.row")
            return link_tags


def write_readme(pecha_id,col):
    Table = "| --- | --- "
    Title = f"|Title | {col['title']} "
    lang = f"|Language | bo"
    source = f"|Source | {input_source}"
    readme = f"{Title}\n{Table}\n{lang}\n{source}"
    with open(f"./opfs/{pecha_id}/readme.md","w") as f:
        f.write(readme)
    return readme


def build(col):
    vols = col['vol']
    pecha_id = get_pecha_id()
    opf_path = f"./opfs/{pecha_id}/{pecha_id}.opf"
    base_id_title_map={}
    for vol in vols:
        if "/library/Book" not in vol['link']:
            continue
        base_id = get_base_id()
        base_id_title_map.update({base_id:[vol['title'],vol['author']]})
        book_id = extract_book_id("http://sakyalibrary.com"+vol['link']) 
        base_text = get_text(book_id)
        create_opf(opf_path,base_text,base_id)
        print(col['title'])
        print(vol['title'])
    col["vol"] = base_id_title_map  
    write_meta(opf_path,col)
    write_readme(pecha_id,col)
    publish_pecha(f"./opfs/{pecha_id}")
    pechas_catalog.info(f"{pecha_id},{col['title']}")

def get_base_id():
    id=uuid4().hex[:4]
    while id.isnumeric() == True:
        id = uuid4().hex[:4]
    return id

def set_up_logger(logger_name):
    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter("%(message)s")
    fileHandler = logging.FileHandler(f"{logger_name}.log")
    fileHandler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(fileHandler)
    return logger


def publish_pecha(opf_path):
    github_utils.github_publish(
    opf_path,
    not_includes=[],
    message="initial commit"
    )
    print("PUBLISHED")


def main():
    global pechas_catalog,err_log
    pechas_catalog = set_up_logger("pechas_catalog")
    err_log = set_up_logger('err')
    for col in get_collections("http://sakyalibrary.com/library/collections"):
        try:
            build(col)
        except:
            err_log.info(f"err :{col['title']}")  


def test_err():
    for col in get_collections("http://sakyalibrary.com/library/collections"):
        build(col)
        break

if __name__ == "__main__":
    main()
    #test_err()
    

