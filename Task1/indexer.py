import argparse
import os
import os.path
import sys
import xml.etree.cElementTree as ET
import re

import msgpack


def tokens_from_string(s):
    return re.compile(r'\w+').findall(s)


def terms_from_tokens(tokens):
    res = []
    for token in tokens:
        if len(token) < 2:
            continue
        res.append(token.lower())

    return res


def get_tokens_from_tree(root):
    if not root.text:
        return []

    tokens = tokens_from_string(root.text)
    result = terms_from_tokens(tokens)
    for child in root:
        result.extend(get_tokens_from_tree(child))

    return result


def get_tokens(path):
    if os.path.splitext(path)[1] == '.xml':
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            print >> sys.stderr, 'Failed to parse', path
            return []
        return get_tokens_from_tree(tree.getroot())
    else:
        print >> sys.stderr, 'Unsupported extension:', path
        return []


def remove_duplicates(sorted_list):
    res = []
    for v in sorted_list:
        if (not res) or res[-1] != v:
            res.append(v)

    return res


def build_inverted_index(corpus_dir):
    docs_list = []
    index = {}
    tokens_count = 0
    print 'Processing documents...'
    i = 0
    for root, dirs, files in os.walk(corpus_dir):
        for name in files:
            path = os.path.join(root, name)
            tokens = get_tokens(path)
            tokens_count += len(tokens)
            if tokens:
                doc_id = len(docs_list)
                docs_list.append(os.path.relpath(path, corpus_dir))
            terms = terms_from_tokens(tokens)
            for term in terms:
                if term not in index:
                    index[term] = []
                index[term].append(doc_id)

            i += 1
            if i % 1000 == 0:
                print 'Processed {} documents'.format(i)

    for k, v in index.iteritems():
        index[k] = remove_duplicates(v)

    print 'Tokens count:', tokens_count
    print 'Terms count:', len(index)

    return docs_list, index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='path to corpus')
    parser.add_argument('-o', '--output', required=True, help='path to store index')
    args = parser.parse_args()
    corpus_dir = args.input
    if not os.path.isdir(corpus_dir):
        sys.stderr.write('Path to corpus must be directory')
        sys.exit(1)

    docs_list, index = build_inverted_index(corpus_dir)

    print 'Saving index...'
    with open(args.output, 'w') as f:
        to_dump = {
            'docs': docs_list,
            'index': index,
        }
        msgpack.dump(to_dump, f)

if __name__ == '__main__':
    main()
