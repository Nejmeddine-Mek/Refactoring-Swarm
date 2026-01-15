from collections import defaultdict
from src.tools.file_tools import read_file

def create_dependency_graph(files):
    files_map = defaultdict(str)
    graph = defaultdict(list)

    # we start by creating keys for our directory
    for f in files:
        graph.setdefault(f.name[:-len(".py")],[])
        files_map.setdefault(f.name[:-len(".py")],f)
    # now, we have to read the files and then catch dependencies to fill the graph

    for f in files:
        # start by reading each file and extracting the imports from it
        content = read_file(f)
        content = [line for line in content.split('\n') if (not line == "") and "import" in line ]
        file_name = f.name[:-len(".py")]
        # now, in each file, we check the sentence after import, and check if it has any key we included
        for line in content:
            words = line.split(" ")
            for key in graph.keys():
                if key in words[1]:
                    graph[file_name].append(files_map.get(key))
    keys = list(graph.keys())
    for key in keys:
        graph[files_map[key]] = graph.pop(key)
        #print(files_map.get(key), " ", graph.get(key))
    return graph