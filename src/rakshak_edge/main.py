import logging

from rakshak_edge.llm import get_llm
from rakshak_edge.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

llm = get_llm()

print(llm.invoke("Hello").content)
