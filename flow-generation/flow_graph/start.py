from llm_config import llm
import code_generation

# with open("../api-docs/yle.txt", "r") as f:
#     yle_api_doc = f.read()
# with open("../api-docs/hotstar.txt", "r") as f:
#     hotstar_api_doc = f.read()
with open("../api-docs/ctv.txt", "r") as f:
    ctv_api_doc = f.read()

instructions = f"""
    You are an expert web crawler\n
    Provided an API documentation, you need to write a python code\n
    to crawl those APIs and get the data in a structured manner\n
    i.e. store them in a hierarchial folder-file format\n
    for example, you have a show, then you should save it like\n
        --showname(dir)\n
            --episode1(file)\n
            --episode2(file)\n
            and so on\n
    And the episode metadata in those files\n

    But, if you don't have shows/episode hierarchy,\n
    and you have movies, then you should store the data in\n
        --movies(dir)\n
            --movie1\n
            --movie2\n
            and so on\n

    IMPORTANT:\n
        1. You need to identify and analyze the data,\n
        and extract only the relevant content.\n
        2. Ignore all the unnecessary data like page styles, etc\n
        3. As you need to get the data in a hierarchial manner, you\n
        should crawl the APIs hierarchially as well\n
            eg. You found a show,\n
                then you first crawl all its episodes,\n
                and then the rest of the shows\n
        4. If a website requires authentication, mention the\n
        required credentials in the code itself\n
        so the user can pass them there and run the code\n
        5. Provide the necessary informations like how to run the file\n
        with the file name using terminal commands etc\n
        6. Store the results in "../result_json" directory\n
        7. Some websites require properties like usertoken/device_id,\n
        so you can mention that in the code to input it, and\n
        crawl using that so that you don't get unauthorized errors\n

        API Documentation\n
        {ctv_api_doc}
"""

code_generation.generate_code(instructions)