from bs4 import BeautifulSoup
import warnings

def parse_webpages(webpage) -> BeautifulSoup:
    """
    Adaptive parsing of the webpage content by html parser or lxml parser.
    """
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            soup = BeautifulSoup(webpage, "html.parser")
            # 检查是否有 XML 解析警告
            if any("XMLParsedAsHTMLWarning" in str(warning.message) for warning in w):
                raise Warning("Detected XML parsed as HTML, switching to XML parser.")
    except Warning:
        # 重新使用 xml 解析器解析
        soup = BeautifulSoup(webpage, "xml")
    return soup