from nltk.tokenize import MWETokenizer
from nltk.util import Trie


class MWETokenizerPlaceholder(MWETokenizer):
    """Extends nltk MWETokenizer by adding tokenize_placeholder function"""

    def tokenize_placeholder(self, text: list[str], placeholder="#") -> list[str]:
        """
        :type text: list(str)
        :param text: A list containing tokenized text

        :type placeholder: str
        :param placeholder: Placeholder character

        :rtype: list(str)
        :return: A list of the tokenized text with multi-words merged together

        :Example:

        >>> tokenizer = MWETokenizer([('feel', '#', 'pain',)], separator='_')
        >>> tokenizer.tokenize_placeholder("To feel his pain".split())
        ['To', 'feel_his_pain']
        """

        i = 0
        n = len(text)
        result = []

        while i < n:
            if text[i] in self._mwes or (text[i] != placeholder and placeholder in self._mwes):
                # possible MWE match
                j = i
                trie = self._mwes
                last_match = -1
                while j < n and (text[j] in trie or (text[j] != placeholder and placeholder in trie)):
                    if text[j] in trie:
                        trie = trie[text[j]]
                    else:
                        trie = trie[placeholder]
                    j += 1
                    if Trie.LEAF in trie:
                        last_match = j

                if last_match > -1:
                    j = last_match

                if Trie.LEAF in trie or last_match > -1:
                    # success!
                    result.append(self._separator.join(text[i:j]))
                    i = j
                else:
                    # no match, so backtrack
                    result.append(text[i])
                    i += 1
            else:
                result.append(text[i])
                i += 1
        return result
