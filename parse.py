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

logging.basicConfig(
    filename="new_pagination_updated.log",
    format="%(message)s",
    level=logging.INFO,
)


text_api = 'http://sakyalibrary.com/library/BookPage?bookId={book_id}&pgNo={page_no}'
main_api = 'http://sakyalibrary.com/library/Book/{book_id}'

def make_request(url):
    response = requests.get(url)
    return response


def get_text(book_id):
    response = make_request(main_api.format(book_id=book_id))
    page = BeautifulSoup(response.content,'html.parser')
    pagination_ul = page.select_one("ul.pagination li#pgNext")
    base_text = get_into_page(book_id)
    return base_text


def get_into_page(book_id,page_no=1,base_text={}):
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


def create_opf(opf_path,base_text,filename):
    opf = OpenPechaFS(opf_path=opf_path)
    layers = {f"v{filename}": {LayerEnum.pagination: get_layers(base_text)}}
    bases = {f"v{filename}":get_base_text(base_text)}
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
        uuid4().hex:Page(span=Span(start=page_start,end=page_end),page_info=page_no)
    }

    return page_annotation,page_end+2


def create_meta(opf_path):
    instance_meta = PechaMetaData(
        initial_creation_type=InitialCreationEnum.input,
        created_at=datetime.now(),
        last_modified_at=datetime.now(),
        source_metadata="")
    opf = OpenPechaFS(opf_path=opf_path)
    opf._meta = instance_meta
    opf.save_meta()


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
            title = link_tag.select_one('div').text
            link = link_tag.select_one('a')['href']
            vols.append({"title":title,"link":link})

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



def main(col):
    vols = col['vol']
    pecha_id = get_pecha_id()
    opf_path = f"./opfs/{pecha_id}/{pecha_id}.opf"

    for vol in vols:
        print(vol['link'])
        if "/library/Book" not in vol['link']:
            continue
        url = "http://sakyalibrary.com"+vol['link']
        filename = vol['title']
        book_id = extract_book_id(url) 
        base_text = get_text(book_id)
        create_opf(opf_path,base_text,filename[0:20])
        print(vol['title'])
    create_meta(opf_path)
    

if __name__ == "__main__":
    for col in get_collections("http://sakyalibrary.com/library/collections"):
        main(col)
        break
