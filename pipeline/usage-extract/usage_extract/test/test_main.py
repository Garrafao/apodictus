import unittest

from usage_extract.helper.text import *


class TestTextCleanMethods(unittest.TestCase):

    def test_remove_tags(self):
        text = "<p>This <i>should</i> be the result<div>!</div></p>"
        text_actual = remove_tags(text)
        text_expected = "This should be the result!"
        self.assertEqual(text_expected, text_actual)

    def test_remove_tags_short_close(self):
        text = "<p>This <i>should</> be the result<div>!</></>"
        text_actual = remove_tags(text)
        text_expected = "This should be the result!"
        self.assertEqual(text_expected, text_actual)

    def test_remove_tags_non_matching_names(self):
        text = "<a>This <b>should<c> be the result<d>!<e><f>"
        text_actual = remove_tags(text)
        text_expected = "This should be the result!"
        self.assertEqual(text_expected, text_actual)

    def test_remove_now_corpus_toolong(self):
        text = "This should**12345;12345;TOOLONG be the result!"
        text_actual = remove_now_corpus_toolong(text)
        text_expected = "This should be the result!"
        self.assertEqual(text_expected, text_actual)

    def test_fix_punctuation_whitespace_symbols(self):
        text = " . , ! ? ; :"
        text_actual = fix_punctuation_whitespace(text)
        text_expected = ".,!?;:"
        self.assertEqual(text_expected, text_actual)

    def test_fix_punctuation_whitespace_sentence(self):
        text = "Easy . This , is too much spacing ! Right ? Overwhelming ; stop it now : really"
        text_actual = fix_punctuation_whitespace(text)
        text_expected = "Easy. This, is too much spacing! Right? Overwhelming; stop it now: really"
        self.assertEqual(text_expected, text_actual)
