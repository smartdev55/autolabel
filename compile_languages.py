import os

supported_languages = ["en_US", "vi_VN", "zh_CN"]

for language in supported_languages:
    # Compile the .ts file into a .qm file
    command = f"lrelease anylabeling/resources/translations/{language}.ts"
    os.system(command)
