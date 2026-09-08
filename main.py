import configparser, requests, sys, subprocess, os
from tqdm import tqdm
from ebooklib import epub
from e621 import E621

help_doc, config_file, chapter_enable, output_folder, chapter_mode, book_init, title_parse = """           
E6PUB - E621 to book converter
------------------------------
-h    -   This documentation
-p    -   Set pool ID (Can accept multiple pool IDs separated by commas.)
-c    -   Set config file location.
-o    -   Set the output folder location (default folder: ./ - current directory)
-s    -   Save multiple pools as a single book (Pools will be divided by chapters. Must manually set title)
-t    -   Title parsing (truncate everything past either: "(", "[", "{", "-", or "by". Removes unwanted title extensions)
------------------------------
This utility is not designed to remove author ownership and assumes that the author is okay with you turning their work
into 
           """, 'config.ini', False, '.', False, False, False


def get_arg(arg_stack = sys.argv, arg_needle = str()):
    if(arg_needle in arg_stack):
        i = 0
        for arg in arg_stack:
            i+=1
            if(arg_needle == arg):
                try:
                    return(arg_stack[i])
                except:
                    return(True)
        return(True)
    else:
        return(False)

def parse_title(title):
    for needle in ['(','[','{','-','by']:
        if(needle in title):
            i = 0
            for word in title.split():
                if(needle in word):
                    i = i
                i+=1
    try:
        return(' '.join(title.split()[:i]))
    except:
        return(' '.join(title.split()))
if(len(sys.argv) < 2):
    pool_int = input("Enter the comics pool id: ")
else: 
    if(get_arg(arg_needle='-h') == True):
        print(help_doc)
        exit()
    if(get_arg(arg_needle='-p') != False):
        pool_int = get_arg(arg_needle='-p')
    if(get_arg(arg_needle='-c') != False):
        config_file = get_arg(arg_needle='-c')
    if(get_arg(arg_needle='-o')):
        output_folder = get_arg(arg_needle='-o')
    if(get_arg(arg_needle='-s')):
        chapter_mode = True
        if(get_arg(arg_needle='--title')): #This seems to be required since it gets cleared at some point which doesn't make sense
                                       #but I don't feel like looking into it very much right now.
            title_override = get_arg(arg_needle='--title')
        else:
            title_override = parse_title(input('Set alernative title: '))
    if(get_arg(arg_needle='-t')):
        title_parse = True
    
config = configparser.ConfigParser()
config.read(str(config_file))
api = E621((f"{config['e621']['username']}", f"{config['e621']['api_key']}"), client_name=f"{config['e621']['client_name']}", client_version=f"{config['e621']['client_version']}")

for pool_id in pool_int.replace(' ','').split(','): #Grabs a single pool ID



    if(book_init == False): #If book is not initialized then initialize it.
        tag_list, book_init, page_num = list(), True, 0
        post_pool, book = api.pools.get(pool_id), epub.EpubBook()

        book.set_identifier(f"{post_pool.id}")
        book.set_title(f"{parse_title(post_pool.name.replace('_',' '))}")
        book.set_language(f"{config['config']['language']}")
        book.add_author(f"{post_pool.creator_name}")
        book.add_metadata("DC","publisher",f"{config['config']['source']}")
        book.add_metadata("DC","date",f"{post_pool.created_at}")

        if(config['config']['mode'] == 'comic'):
            book.add_metadata("DC", "description", f"{post_pool.description}")


    if(chapter_mode == True and 'page_num' == 0): #This is used to rename the book because iterating through pools would rename the book each time.
                                                             #This requests that the page is not initialized since if it is the program will restart from 1
                                                             #and will cause a duplication issue instead of continuing to iterate.
        page_num, book_init = 0, False

        if(get_arg(arg_needle='--title')):
            title_override = get_arg(arg_needle='--title')
            book.set_title(title_override)
        else:
            title_override = input('Enter book title: ')
            book.set_title(title_override)
    else:
        post_pool = api.pools.get(pool_id) #This is to iterate to the next chapter
    for post_id in tqdm(post_pool.post_ids): #Grabs a single post from the pool and iterates the progress bar.
        
        post = api.posts.get(post_id=post_id)
        
        for tag in post.all_tags: #Adds a searchable tag to a tag array and saves across all iterated posts.
            if tag not in tag_list:
                tag_list.append(f"{tag}")

        page_num+=1
        try: #Sometimes there are deleted images in a pool, so this skips them
            request_data = requests.get(post.file.url).content
            img = epub.EpubImage(uid=f"{post.id}", file_name=f"static/{post.id}.{post.file.ext}", media_type=f"image/{post.file.ext}", content=request_data)
            book.add_item(img)

            if(page_num==1): #Sets the cover as the first page of the book.
                page = epub.EpubHtml(title="Cover", file_name="cover_wp.xhtml", lang=f"{config['config']['language']}")
                book.set_cover(file_name=f"static/cover.{post.file.ext}",content=request_data)
            else: #Sets all other pages as standard pages
                page = epub.EpubHtml(title=f"{page_num-1}", file_name=f"{page_num}.xhtml", lang=f"{config['config']['language']}")
        
            if(config['config']['orientation'] == 'landscape'): #Format the pages to fit an ereader (tested on a Kindle Touch)
                page.content = (f'<p><img alt="Comic Page" style="height: 100vh; width:90vw;" src="static/{post.id}.{post.file.ext}"/></p>')
            else:
                page.content = (f'<p><img alt="Comic Page" style="height: 100vh; width:90vw; transform: rotate(90deg);" src="static/{post.id}.{post.file.ext}"/></p>')

            book.add_item(page)
            book.spine.append(page)
            subprocess.call('clear' if os.name == 'posix' else 'cls')
            print(f"Name: {post_pool.name.replace('_',' ')} - Page: {page_num} - Source: https://e621.net/posts/{post.id}") #Shows the description of the current process.
        except:
            print(f"Name: {post_pool.name.replace('_',' ')} - Page: {page_num} - Source: https://e621.net/posts/{post.id} - invalid/deleted")
            pass
    if(chapter_mode==False): #A shameful but simple way to save a book while not in chapter mode.
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.add_metadata("DC", "subject", f"{','.join(tag_list)}")
        epub.write_epub(f"{post_pool.name.replace('_',' ')}.epub", book)
        print(f"{output_folder}/{post_pool.name.replace('_',' ')}.epub")
        page_num, book_init = 0, False
if(chapter_mode==True): #Ditto as the last comment, but instead this is for when the program IS in chapter mode.
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.add_metadata("DC", "subject", f"{','.join(tag_list)}")
    epub.write_epub(f"{title_override}.epub", book)
    print(f"{output_folder}/{title_override}.epub")
