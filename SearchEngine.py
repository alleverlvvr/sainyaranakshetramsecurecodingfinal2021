{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 1,
   "metadata": {},
   "outputs": [],
   "source": [
    "#Basic Search engine by Rahul Shaw\n",
    "#Capable of searching a document or a list of documents on addition of them by indexing\n",
    "#Capable of adding new data\n",
    "#Shows duration of search\n",
    "#Shows id along with data\n",
    "#Removes unnecessary words for better accuracy\n",
    "#Sorts results based on score\n",
    "#Work atomically with files\n",
    "#Safer\n",
    "#Converts into json for document generation\n",
    "#Autocorrects search query in any Upper or lower or mix case\n",
    "\n",
    "from __future__ import print_function\n",
    "import glob\n",
    "import os\n",
    "import shutil\n",
    "import sys\n",
    "import hashlib\n",
    "import json\n",
    "import math\n",
    "import os\n",
    "import re\n",
    "import tempfile\n",
    "\n",
    "class Microsearch(object):\n",
    "    \"\"\"\n",
    "    Controls the indexing/searching of documents.\n",
    "    \"\"\"\n",
    "    # A fairly standard list of \"stopwords\", which are words that contribute little\n",
    "    # to relevance (since they are so common in English) & are to be ignored.\n",
    "    STOP_WORDS = set([\n",
    "        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by',\n",
    "        'for', 'if', 'in', 'into', 'is', 'it',\n",
    "        'no', 'not', 'of', 'on', 'or', 's', 'such',\n",
    "        't', 'that', 'the', 'their', 'then', 'there', 'these',\n",
    "        'they', 'this', 'to', 'was', 'will', 'with'\n",
    "    ])\n",
    "    PUNCTUATION = re.compile('[~`!@#$%^&*()+={\\[}\\]|\\\\:;\"\\',<.>/?]')\n",
    "\n",
    "    def __init__(self, base_directory):\n",
    "        \"\"\"\n",
    "        Sets up the object & the data directory.\n",
    "        Requires a ``base_directory`` parameter, which specifies the parent\n",
    "        directory the index/document/stats data will be kept in.\n",
    "        Example::\n",
    "            ms = Microsearch('/var/my_index')\n",
    "        \"\"\"\n",
    "        self.base_directory = base_directory\n",
    "        self.index_path = os.path.join(self.base_directory, 'index')\n",
    "        self.docs_path = os.path.join(self.base_directory, 'documents')\n",
    "        self.stats_path = os.path.join(self.base_directory, 'stats.json')\n",
    "        self.setup()\n",
    "\n",
    "    def setup(self):\n",
    "        \"\"\"\n",
    "        Handles the creation of the various data directories.\n",
    "        If the paths do not exist, it will create them. As a side effect, you\n",
    "        must have read/write access to the location you're trying to create\n",
    "        the data at.\n",
    "        \"\"\"\n",
    "        if not os.path.exists(self.base_directory):\n",
    "            os.makedirs(self.base_directory)\n",
    "\n",
    "        if not os.path.exists(self.index_path):\n",
    "            os.makedirs(self.index_path)\n",
    "\n",
    "        if not os.path.exists(self.docs_path):\n",
    "            os.makedirs(self.docs_path)\n",
    "\n",
    "        return True\n",
    "\n",
    "    def read_stats(self):\n",
    "        \"\"\"\n",
    "        Reads the index-wide stats.\n",
    "        If the stats do not exist, it makes returns data with the current\n",
    "        version of ``microsearch`` & zero docs (used in scoring).\n",
    "        \"\"\"\n",
    "        if not os.path.exists(self.stats_path):\n",
    "            return {\n",
    "                'version': '.'.join([str(bit) for bit in __version__]),\n",
    "                'total_docs': 0,\n",
    "            }\n",
    "\n",
    "        with open(self.stats_path, 'r') as stats_file:\n",
    "            return json.load(stats_file)\n",
    "\n",
    "    def write_stats(self, new_stats):\n",
    "        \"\"\"\n",
    "        Writes the index-wide stats.\n",
    "        Takes a ``new_stats`` parameter, which should be a dictionary of\n",
    "        stat data. Example stat data::\n",
    "            {\n",
    "                'version': '1.0.0',\n",
    "                'total_docs': 25,\n",
    "            }\n",
    "        \"\"\"\n",
    "        with open(self.stats_path, 'w') as stats_file:\n",
    "            json.dump(new_stats, stats_file)\n",
    "\n",
    "        return True\n",
    "\n",
    "    def increment_total_docs(self):\n",
    "        \"\"\"\n",
    "        Increments the total number of documents the index is aware of.\n",
    "        This is important for scoring reasons & is typically called as part\n",
    "        of the indexing process.\n",
    "        \"\"\"\n",
    "        current_stats = self.read_stats()\n",
    "        current_stats.setdefault('total_docs', 0)\n",
    "        current_stats['total_docs'] += 1\n",
    "        self.write_stats(current_stats)\n",
    "\n",
    "    def get_total_docs(self):\n",
    "        \"\"\"\n",
    "        Returns the total number of documents the index is aware of.\n",
    "        \"\"\"\n",
    "        current_stats = self.read_stats()\n",
    "        return int(current_stats.get('total_docs', 0))\n",
    "\n",
    "\n",
    "    # ==============================\n",
    "    # Tokenization & Term Generation\n",
    "    # ==============================\n",
    "\n",
    "    def make_tokens(self, blob):\n",
    "        \"\"\"\n",
    "        Given a string (``blob``) of text, this will return a list of tokens.\n",
    "        This generally/loosely follows English sentence construction, replacing\n",
    "        most punctuation with spaces, splitting on whitespace & omitting any\n",
    "        tokens in ``self.STOP_WORDS``.\n",
    "        You can customize behavior by overriding ``STOP_WORDS`` or\n",
    "        ``PUNCTUATION`` in a subclass.\n",
    "        \"\"\"\n",
    "        # Kill the punctuation.\n",
    "        blob = self.PUNCTUATION.sub(' ', blob)\n",
    "        tokens = []\n",
    "\n",
    "        # Split on spaces.\n",
    "        for token in blob.split():\n",
    "            # Make sure everything is in lowercase & whitespace removed.\n",
    "            token = token.lower().strip()\n",
    "\n",
    "            if not token in self.STOP_WORDS:\n",
    "                tokens.append(token)\n",
    "\n",
    "        return tokens\n",
    "\n",
    "    def make_ngrams(self, tokens, min_gram=3, max_gram=6):\n",
    "        \"\"\"\n",
    "        Converts a iterable of ``tokens`` into n-grams.\n",
    "        This assumes front grams (all grams made starting from the left side\n",
    "        of the token).\n",
    "        Optionally accepts a ``min_gram`` parameter, which takes an integer &\n",
    "        controls the minimum gram length. Default is ``3``.\n",
    "        Optionally accepts a ``max_gram`` parameter, which takes an integer &\n",
    "        controls the maximum gram length. Default is ``6``.\n",
    "        \"\"\"\n",
    "        terms = {}\n",
    "\n",
    "        for position, token in enumerate(tokens):\n",
    "            for window_length in range(min_gram, min(max_gram + 1, len(token) + 1)):\n",
    "                # Assuming \"front\" grams.\n",
    "                gram = token[:window_length]\n",
    "                terms.setdefault(gram, [])\n",
    "\n",
    "                if not position in terms[gram]:\n",
    "                    terms[gram].append(position)\n",
    "\n",
    "        return terms\n",
    "\n",
    "\n",
    "    # ================\n",
    "    # Segment Handling\n",
    "    # ================\n",
    "\n",
    "    def hash_name(self, term, length=6):\n",
    "        \"\"\"\n",
    "        Given a ``term``, hashes it & returns a string of the first N letters.\n",
    "        Optionally accepts a ``length`` parameter, which takes an integer &\n",
    "        controls how much of the hash is returned. Default is ``6``.\n",
    "        This is usefully when writing files to the file system, as it helps\n",
    "        us keep from putting too many files in a given directory (~32K max\n",
    "        with the default).\n",
    "        \"\"\"\n",
    "        # Make sure it's ASCII to appease the hashlib gods.\n",
    "        term = term.encode('ascii', errors='ignore')\n",
    "        # We hash & slice the term to get a small-ish number of fields\n",
    "        # and good distribution between them.\n",
    "        hashed = hashlib.md5(term).hexdigest()\n",
    "        return hashed[:length]\n",
    "\n",
    "    def make_segment_name(self, term):\n",
    "        \"\"\"\n",
    "        Given a ``term``, creates a segment filename based on the hash of the term.\n",
    "        Returns the full path to the segment.\n",
    "        \"\"\"\n",
    "        return os.path.join(self.index_path, \"{0}.index\".format(self.hash_name(term)))\n",
    "\n",
    "    def parse_record(self, line):\n",
    "        \"\"\"\n",
    "        Given a ``line`` from the segment file, this returns the term & its info.\n",
    "        The term info is stored as serialized JSON. The default separator\n",
    "        between the term & info is the ``\\t`` character, which would never\n",
    "        appear in a term due to the way tokenization is done.\n",
    "        \"\"\"\n",
    "        return line.rstrip().split('\\t', 1)\n",
    "\n",
    "    def make_record(self, term, term_info):\n",
    "        \"\"\"\n",
    "        Given a ``term`` and a dict of ``term_info``, creates a line for\n",
    "        writing to the segment file.\n",
    "        \"\"\"\n",
    "        return \"{0}\\t{1}\\n\".format(term, json.dumps(term_info, ensure_ascii=False))\n",
    "\n",
    "    def update_term_info(self, orig_info, new_info):\n",
    "        \"\"\"\n",
    "        Takes existing ``orig_info`` & ``new_info`` dicts & combines them\n",
    "        intelligently.\n",
    "        Used for updating term_info within the segments.\n",
    "        \"\"\"\n",
    "        # Updates are (sadly) not as simple as ``dict.update()``.\n",
    "        # Iterate through the keys (documents) & manually update.\n",
    "        for doc_id, positions in new_info.items():\n",
    "            if not doc_id in orig_info:\n",
    "                # Easy case; it's not there. Shunt it in wholesale.\n",
    "                orig_info[doc_id] = positions\n",
    "            else:\n",
    "                # Harder; it's there. Convert to sets, update then convert back\n",
    "                # to lists to accommodate ``json``.\n",
    "                orig_positions = set(orig_info.get(doc_id, []))\n",
    "                new_positions = set(positions)\n",
    "                orig_positions.update(new_positions)\n",
    "                orig_info[doc_id] = list(orig_positions)\n",
    "\n",
    "        return orig_info\n",
    "\n",
    "    def save_segment(self, term, term_info, update=False):\n",
    "        \"\"\"\n",
    "        Writes out new index data to disk.\n",
    "        Takes a ``term`` string & ``term_info`` dict. It will\n",
    "        rewrite the segment in alphabetical order, adding in the data\n",
    "        where appropriate.\n",
    "        Optionally takes an ``update`` parameter, which is a boolean &\n",
    "        determines whether the provided ``term_info`` should overwrite or\n",
    "        update the data in the segment. Default is ``False`` (overwrite).\n",
    "        \"\"\"\n",
    "        seg_name = self.make_segment_name(term)\n",
    "        new_seg_file = tempfile.NamedTemporaryFile(delete=False)\n",
    "        written = False\n",
    "\n",
    "        if not os.path.exists(seg_name):\n",
    "            # If it doesn't exist, touch it.\n",
    "            with open(seg_name, 'w') as seg_file:\n",
    "                seg_file.write('')\n",
    "\n",
    "        with open(seg_name, 'r') as seg_file:\n",
    "            for line in seg_file:\n",
    "                seg_term, seg_term_info = self.parse_record(line)\n",
    "\n",
    "                if not written and seg_term > term:\n",
    "                    # We're at the alphabetical location & need to insert.\n",
    "                    new_line = self.make_record(term, term_info)\n",
    "                    new_seg_file.write(new_line.encode('utf-8'))\n",
    "                    written = True\n",
    "                elif seg_term == term:\n",
    "                    if not update:\n",
    "                        # Overwrite the line for the update.\n",
    "                        line = self.make_record(term, term_info)\n",
    "                    else:\n",
    "                        # Update the existing record.\n",
    "                        new_info = self.update_term_info(json.loads(seg_term_info), term_info)\n",
    "                        line = self.make_record(term, new_info)\n",
    "\n",
    "                    written = True\n",
    "\n",
    "                # Either we haven't reached it alphabetically or we're well-past.\n",
    "                # Write the line.\n",
    "                new_seg_file.write(line.encode('utf-8'))\n",
    "\n",
    "            if not written:\n",
    "                line = self.make_record(term, term_info)\n",
    "                new_seg_file.write(line.encode('utf-8'))\n",
    "\n",
    "        # Atomically move it into place.\n",
    "        new_seg_file.close()\n",
    "        try:\n",
    "            os.rename(new_seg_file.name, seg_name)\n",
    "        except OSError:\n",
    "            os.remove(seg_name)\n",
    "            os.rename(new_seg_file.name, seg_name)\n",
    "        return True\n",
    "\n",
    "    def load_segment(self, term):\n",
    "        \"\"\"\n",
    "        Given a ``term``, this will return the ``term_info`` associated with\n",
    "        the ``term``.\n",
    "        If no index file exists or the term is not found, this returns an\n",
    "        empty dict.\n",
    "        \"\"\"\n",
    "        seg_name = self.make_segment_name(term)\n",
    "\n",
    "        if not os.path.exists(seg_name):\n",
    "            return {}\n",
    "\n",
    "        with open(seg_name, 'r') as seg_file:\n",
    "            for line in seg_file:\n",
    "                seg_term, term_info = self.parse_record(line)\n",
    "\n",
    "                if seg_term == term:\n",
    "                    # Found it.\n",
    "                    return json.loads(term_info)\n",
    "\n",
    "        return {}\n",
    "\n",
    "\n",
    "    # =================\n",
    "    # Document Handling\n",
    "    # =================\n",
    "\n",
    "    def make_document_name(self, doc_id):\n",
    "        \"\"\"\n",
    "        Given a ``doc_id``, this constructs a path where the document should\n",
    "        be stored.\n",
    "        It uses a similar hashing mechanism as ``make_segment_name``, using\n",
    "        the hash fragment to control the directory structure instead of the\n",
    "        filename.\n",
    "        Returns the full filepath to the document.\n",
    "        \"\"\"\n",
    "        # Builds a path like ``BASE_DIR/documents/5d4140/hello.json``.\n",
    "        return os.path.join(self.docs_path, self.hash_name(doc_id), \"{0}.json\".format(doc_id))\n",
    "\n",
    "    def save_document(self, doc_id, document):\n",
    "        \"\"\"\n",
    "        Given a ``doc_id`` string & a ``document`` dict, writes the document to\n",
    "        disk.\n",
    "        Uses JSON as the serialization format.\n",
    "        \"\"\"\n",
    "        doc_path = self.make_document_name(doc_id)\n",
    "        base_path = os.path.dirname(doc_path)\n",
    "\n",
    "        if not os.path.exists(base_path):\n",
    "            os.makedirs(base_path)\n",
    "\n",
    "        with open(doc_path, 'w') as doc_file:\n",
    "            doc_file.write(json.dumps(document, ensure_ascii=False))\n",
    "\n",
    "        return True\n",
    "\n",
    "    def load_document(self, doc_id):\n",
    "        \"\"\"\n",
    "        Given a ``doc_id`` string, loads a given document from disk.\n",
    "        Raises an exception if the document no longer exists.\n",
    "        Returns the document data as a dict.\n",
    "        \"\"\"\n",
    "        doc_path = self.make_document_name(doc_id)\n",
    "\n",
    "        with open(doc_path, 'r') as doc_file:\n",
    "            data = json.loads(doc_file.read())\n",
    "\n",
    "        return data\n",
    "\n",
    "\n",
    "    def index(self, doc_id, document):\n",
    "        \"\"\"\n",
    "        Given a ``doc_id`` string & a ``document`` dict, does everything needed\n",
    "        to save & index the document for searching.\n",
    "        The ``document`` dict must have a ``text`` key, which should contain the\n",
    "        blob to be indexed. All other fields are simply stored.\n",
    "        Returns ``True`` on success.\n",
    "        \"\"\"\n",
    "        # Ensure that the ``document`` looks like a dictionary.\n",
    "        if not hasattr(document, 'items'):\n",
    "            raise AttributeError('You must provide `index` with a document in the form of a dictionary.')\n",
    "\n",
    "        # For example purposes, we only index the ``text`` field.\n",
    "        if not 'text' in document:\n",
    "            raise KeyError('You must provide `index` with a document with a `text` field in it.')\n",
    "\n",
    "        # Make sure the document ID is a string.\n",
    "        doc_id = str(doc_id)\n",
    "        self.save_document(doc_id, document)\n",
    "\n",
    "        # Start analysis & indexing.\n",
    "        tokens = self.make_tokens(document.get('text', ''))\n",
    "        terms = self.make_ngrams(tokens)\n",
    "\n",
    "        for term, positions in terms.items():\n",
    "            self.save_segment(term, {doc_id: positions}, update=True)\n",
    "\n",
    "        self.increment_total_docs()\n",
    "        return True\n",
    "\n",
    "\n",
    "    # =========\n",
    "    # Searching\n",
    "    # =========\n",
    "\n",
    "    def parse_query(self, query):\n",
    "        \"\"\"\n",
    "        Given a ``query`` string, converts it into terms for searching in the\n",
    "        index.\n",
    "        Returns a list of terms.\n",
    "        \"\"\"\n",
    "        tokens = self.make_tokens(query)\n",
    "        return self.make_ngrams(tokens)\n",
    "\n",
    "    def collect_results(self, terms):\n",
    "        \"\"\"\n",
    "        For a list of ``terms``, collects all the documents from the index\n",
    "        containing those terms.\n",
    "        The returned data is a tuple of two dicts. This is done to make the\n",
    "        process of scoring easy & require no further information.\n",
    "        The first dict contains all the terms as keys & a count (integer) of\n",
    "        the matching docs as values.\n",
    "        The second dict inverts this, with ``doc_ids`` as the keys. The values\n",
    "        are a nested dict, which contains the ``terms`` as the keys and a\n",
    "        count of the number of positions within that doc.\n",
    "        Since this is complex, an example return value::\n",
    "            >>> per_term_docs, per_doc_counts = ms.collect_results(['hello', 'world'])\n",
    "            >>> per_term_docs\n",
    "            {\n",
    "                'hello': 2,\n",
    "                'world': 1\n",
    "            }\n",
    "            >>> per_doc_counts\n",
    "            {\n",
    "                'doc-1': {\n",
    "                    'hello': 4\n",
    "                },\n",
    "                'doc-2': {\n",
    "                    'hello': 1,\n",
    "                    'world': 3\n",
    "                }\n",
    "            }\n",
    "        \"\"\"\n",
    "        per_term_docs = {}\n",
    "        per_doc_counts = {}\n",
    "\n",
    "        for term in terms:\n",
    "            term_matches = self.load_segment(term)\n",
    "\n",
    "            per_term_docs.setdefault(term, 0)\n",
    "            per_term_docs[term] += len(term_matches.keys())\n",
    "\n",
    "            for doc_id, positions in term_matches.items():\n",
    "                per_doc_counts.setdefault(doc_id, {})\n",
    "                per_doc_counts[doc_id].setdefault(term, 0)\n",
    "                per_doc_counts[doc_id][term] += len(positions)\n",
    "\n",
    "        return per_term_docs, per_doc_counts\n",
    "\n",
    "    def bm25_relevance(self, terms, matches, current_doc, total_docs, b=0, k=1.2):\n",
    "        \"\"\"\n",
    "        Given multiple inputs, performs a BM25 relevance calculation for a\n",
    "        given document.\n",
    "        ``terms`` should be a list of terms.\n",
    "        ``matches`` should be the first dictionary back from\n",
    "        ``collect_results``.\n",
    "        ``current_doc`` should be the second dictionary back from\n",
    "        ``collect_results``.\n",
    "        ``total_docs`` should be an integer of the total docs in the index.\n",
    "        Optionally accepts a ``b`` parameter, which is an integer specifying\n",
    "        the length of the document. Since it doesn't vastly affect the score,\n",
    "        the default is ``0``.\n",
    "        Optionally accepts a ``k`` parameter. It accepts a float & is used to\n",
    "        modify scores to fall into a given range. With the default of ``1.2``,\n",
    "        scores typically range from ``0.4`` to ``1.0``.\n",
    "        \"\"\"\n",
    "        # More or less borrowed from http://sphinxsearch.com/blog/2010/08/17/how-sphinx-relevance-ranking-works/.\n",
    "        score = b\n",
    "\n",
    "        for term in terms:\n",
    "            idf = math.log((total_docs - matches[term] + 1.0) / matches[term]) / math.log(1.0 + total_docs)\n",
    "            score = score + current_doc.get(term, 0) * idf / (current_doc.get(term, 0) + k)\n",
    "\n",
    "        return 0.5 + score / (2 * len(terms))\n",
    "\n",
    "    def search(self, query, offset=0, limit=20):\n",
    "        \"\"\"\n",
    "        Given a ``query``, performs a search on the index & returns the results.\n",
    "        Optionally accepts an ``offset`` parameter, which is an integer &\n",
    "        controls what the starting point in the results is. Default is ``0``\n",
    "        (the beginning).\n",
    "        Optionally accepts a ``limit`` parameter, which is an integer &\n",
    "        controls how many results to return. Default is ``20``.\n",
    "        Returns a dictionary containing the ``total_hits`` (integer), which is\n",
    "        a count of all the documents that matched, and ``results``, which is\n",
    "        a list of results (in descending ``score`` order) & sliced to the\n",
    "        provided ``offset/limit`` combination.\n",
    "        \"\"\"\n",
    "        results = {\n",
    "            'total_hits': 0,\n",
    "            'results': []\n",
    "        }\n",
    "\n",
    "        if not len(query):\n",
    "            return results\n",
    "\n",
    "        total_docs = self.get_total_docs()\n",
    "\n",
    "        if total_docs == 0:\n",
    "            return results\n",
    "\n",
    "        terms = self.parse_query(query)\n",
    "        per_term_docs, per_doc_counts = self.collect_results(terms)\n",
    "        scored_results = []\n",
    "        final_results = []\n",
    "\n",
    "        # Score the results per document.\n",
    "        for doc_id, current_doc in per_doc_counts.items():\n",
    "            scored_results.append({\n",
    "                'id': doc_id,\n",
    "                'score': self.bm25_relevance(terms, per_term_docs, current_doc, total_docs),\n",
    "            })\n",
    "\n",
    "        # Sort based on score.\n",
    "        sorted_results = sorted(scored_results, key=lambda res: res['score'], reverse=True)\n",
    "        results['total_hits'] = len(sorted_results)\n",
    "\n",
    "        # Slice the results.\n",
    "        sliced_results = sorted_results[offset:offset + limit]\n",
    "\n",
    "        # For each result, load up the doc & update the dict.\n",
    "        for res in sliced_results:\n",
    "            doc_dict = self.load_document(res['id'])\n",
    "            doc_dict.update(res)\n",
    "            results['results'].append(doc_dict)\n",
    "\n",
    "        return results\n",
    "    def search_data(ms):\n",
    "        queries = []\n",
    "        per_search_times = []\n",
    "        for query in queries:\n",
    "            print(\"Running query `{}`...\".format(query))\n",
    "            start_time = time.time()\n",
    "            results = ms.search(query)\n",
    "            time_taken = time.time() - start_time\n",
    "            print(\"Found {} results in {:.03f} seconds.\".format(results.get('total_hits', 0), time_taken))\n",
    "            per_search_times.append(time_taken)\n",
    "        return per_search_times\n",
    "\n",
    "\n",
    "    def main(enron_data_dir):\n",
    "        data_dir = '/tmp/enron_index'\n",
    "        shutil.rmtree(data_dir, ignore_errors=True)\n",
    "        ms = Microsearch(data_dir)\n",
    "    \n",
    "        print(\"Collecting the emails...\")\n",
    "        globby = os.path.join(enron_data_dir, '*/*/*.')\n",
    "        all_emails = glob.glob(globby)[:1200]\n",
    "    \n",
    "        print(\"Starting indexing {0} docs...\".format(len(all_emails)))\n",
    "        start_time = time.time()\n",
    "        per_doc_times = index_emails(ms, all_emails, enron_data_dir)\n",
    "        time_to_index = time.time() - start_time\n",
    "\n",
    "        per_doc_avg = sum(per_doc_times) / len(per_doc_times)\n",
    "\n",
    "        print(\"Indexing complete.\")\n",
    "        print(\"Total time taken: {:.03f} seconds\".format(time_to_index))\n",
    "        print(\"Avg time per doc: {:.03f} seconds\".format(per_doc_avg))\n",
    "\n",
    "        print(\"Starting searching...\")\n",
    "        start_time = time.time()\n",
    "        per_search_times = search_emails(ms)\n",
    "        time_to_search = time.time() - start_time\n",
    "\n",
    "        per_search_avg = sum(per_search_times) / len(per_search_times)\n",
    "    \n",
    "        print(\"Searching complete.\")\n",
    "        print(\"Total time taken: {:.03f} seconds\".format(time_to_search))\n",
    "        print(\"Avg time per query: {:.03f} seconds\".format(per_search_avg))"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import time\n",
    "\n",
    "ms = Microsearch('/tmp/SearchEngine')\n",
    "\n",
    "file=open('ab.json',encoding='utf8') #scanning data from a file ab.json\n",
    "read = file.read()\n",
    "file.seek(0)\n",
    "read\n",
    "line = 1\n",
    "for word in read:\n",
    "    if word == '\\n':\n",
    "        line=+1\n",
    "array = []\n",
    "for i in range(line):\n",
    "    array.append(file.readline())\n",
    "\n",
    "string=' '.join([str(item) for item in array])    \n",
    "\n",
    "# Index some data.\n",
    "ms.index('data', {'text': 'How do you feel about becoming Management?\\n\\nThe Bobs'})\n",
    "ms.index('new', {'text': string})\n",
    "search = input(\"search: \")\n",
    "# Search on it.\n",
    "start = time.time()\n",
    "print(ms.search(search))\n",
    "end = time.time() #calculating time\n",
    "print(f\"Time is {end-start}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.5"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
