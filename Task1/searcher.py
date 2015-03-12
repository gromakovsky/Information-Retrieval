import argparse
import os.path
import sys
import xml.etree.cElementTree as ET
import re

import msgpack
from pyparsing import Word, alphanums, Forward, CaselessKeyword, Literal, ZeroOrMore, Optional


def exit_with_invalid_serialization_format():
    sys.stderr.write('Invalid serialization format')
    sys.exit(1)


def parse_query(query):
    expr_stack = []

    """
    multop  :: 'and'
    addop   :: 'or'
    unaryop :: 'not'
    word    :: alphanum+
    atom    :: word | '(' + expr + ')
    term    :: atom [multop atom]*
    expr    :: term [addop term]*
    """
    def push_first(strg, loc, toks):
        expr_stack.append(toks[0])

    def push_unary(strg, loc, toks):
        if toks and toks[0] == 'not':
            expr_stack.append('not')

    expr = Forward()
    multop = CaselessKeyword('and')
    addop = CaselessKeyword('or')
    unaryop = CaselessKeyword('not')
    word = Word(alphanums)
    atom = (Optional(unaryop) + word.setParseAction(push_first)
            | (Literal('(') + expr + Literal(')')))\
        .setParseAction(push_unary)
    term = atom + ZeroOrMore((multop + atom).setParseAction(push_first))
    expr << (term + ZeroOrMore((addop + term).setParseAction(push_first)))

    expr.parseString(query)

    return expr_stack


def unite_sorted_lists(list1, list2):
    res = []
    p1, p2 = 0, 0
    while p1 < len(list1) and p2 < len(list2):
        if list1[p1] == list2[p2]:
            res.append(list1[p1])
            p1 += 1
            p2 += 1
        elif list1[p1] < list2[p2]:
            res.append(list1[p1])
            p1 += 1
        else:
            res.append(list2[p2])
            p2 += 1

    while p1 < len(list1):
        res.append(list1[p1])
        p1 += 1

    while p2 < len(list2):
        res.append(list2[p2])
        p2 += 1

    return res


def intersect_sorted_lists(list1, list2):
    res = []
    p1, p2 = 0, 0
    while p1 < len(list1) and p2 < len(list2):
        if list1[p1] == list2[p2]:
            res.append(list1[p1])
            p1 += 1
            p2 += 1
        elif list1[p1] < list2[p2]:
            p1 += 1
        else:
            p2 += 1

    return res


def search(index, query):
    expr_stack = parse_query(query)

    def evaluate_stack():
        top = expr_stack.pop()
        if top == 'and':
            return intersect_sorted_lists(evaluate_stack(), evaluate_stack())
        elif top == 'or':
            return unite_sorted_lists(evaluate_stack(), evaluate_stack())
        elif top == 'not':
            pass    # TODO
        else:
            term = top.lower()
            return index[term] if term in index else []

    return evaluate_stack()


def collect_sentences(filename):
    tree = ET.parse(filename)

    def do_collect(root):
        res = [root.text]
        for child in root:
            res.extend(do_collect(child))

        return res

    sentences = []
    for text in do_collect(tree.getroot()):
        sentences.extend(text.split('.'))

    return sentences


def generate_snippet(query, filename):
    res = ''
    sentences = collect_sentences(filename)
    max_sentences_to_print = 3
    printed = 0
    for word in re.compile('\w+').findall(query.lower()):
        if word in ('and', 'or', 'not'):
            continue
        for sentence in sentences:
            if word in sentence.lower():
                res += '> {} \n'.format(sentence)
                printed += 1
                if printed == max_sentences_to_print:
                    return res
                break

    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--corpus', required=True, help='path to corpus')
    parser.add_argument('-i', '--index', required=True, help='path to index')
    args = parser.parse_args()
    corpus_dir = args.corpus
    if not os.path.isdir(corpus_dir):
        sys.stderr.write('Path to corpus must be directory')
        sys.exit(1)

    with open(args.index) as f:
        o = msgpack.load(f)
        if not isinstance(o, dict):
            exit_with_invalid_serialization_format()
        docs_list = o.get('docs')
        index = o.get('index')
        if docs_list is None or index is None:
            exit_with_invalid_serialization_format()

    print 'Enter query:'
    query = sys.stdin.readline()
    print 'Searching...'
    res_ids = search(index, query)
    print 'Found {} results:'.format(len(res_ids))
    max_results_to_print = 10
    printed = 0
    for doc_id in res_ids:
        doc = docs_list[doc_id]
        print 'Document:', doc
        print generate_snippet(query, os.path.join(corpus_dir, doc))
        print '------------------------------'
        printed += 1
        if printed == max_results_to_print:
            break


if __name__ == '__main__':
    main()
