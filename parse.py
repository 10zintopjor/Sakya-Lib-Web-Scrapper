import re
from traceback import print_tb
from urllib import response
import requests
from bs4 import BeautifulSoup
import re


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
    with open("demo.txt","w") as f:
        f.write(base_text)

    

def get_into_page(book_id,page_no=1):
    response = make_request(text_api.format(book_id=book_id,page_no=page_no))
    base_text=response.text
    if has_next_page(book_id,page_no+1):
        base_text+=get_into_page(book_id,page_no+1)
    else:
        return base_text

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

def main():
    url = "http://sakyalibrary.com/library/Book/68d456e5-5314-4465-a02d-54a10c5b0adb"
    book_id = extract_book_id(url)
    get_text(book_id)

if __name__ == "__main__":
    main()
