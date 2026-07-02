"""Pytest bootstrap for the smoke-test suite.

Two jobs, both done at import time (before any test module is collected):

1. Provide dummy values for the environment variables ``config.validate_core_config``
   / ``require_env`` insist on, so importing the app's modules doesn't ``st.stop``.
2. Stub the deployment-only heavy dependencies (Supabase connector, Azure DI,
   Vertex, FAISS, Pinecone, Prophet, ...) that aren't installed in every dev/CI
   environment, so ``import agents.<x>`` works without them. A meta-path finder is
   *appended* to sys.meta_path, so genuinely-installed packages always win and only
   the missing heavy deps are stubbed.

Living at the repo root, this file also puts the repo root on sys.path so the tests
can ``import config`` / ``import agents.base`` etc.
"""

import importlib.abc
import importlib.machinery
import os
import sys
import types

# 1) Dummy env so config/require_env are satisfied during tests.
_DUMMY_ENV = {
    "AZURE_OPENAI_KEY": "test-key",
    "AZURE_OPENAI_ENDPOINT": "https://azure.example.test",
    "AZURE_OPENAI_DEPLOYMENT_NAME": "test-deployment",
    "AZURE_DI_ENDPOINT": "https://di.example.test",
    "AZURE_DI_KEY": "test-di-key",
    "DEEPSEEK_API_KEY": "test-deepseek",
    "FMP_API_KEY": "test-fmp",
    "OPENAI_API_KEY": "test-openai",
    "EODHD_API_KEY": "test-eodhd",
    "TAVILY_API_KEY": "test-tavily",
    "PINECONE_API_KEY": "test-pinecone",
    "SUPABASE_URL": "https://supabase.example.test",
    "SUPABASE_KEY": "test-supabase-key",
    "APP_ADMIN_PASSWORD": "test-admin",
}
for _k, _v in _DUMMY_ENV.items():
    os.environ.setdefault(_k, _v)

# 2) Stub heavy, deployment-only dependencies if they are not installed.
_STUB_ROOTS = {
    "st_supabase_connection", "supabase", "vertexai", "faiss",
    "sentence_transformers", "pinecone", "fitz", "pdfplumber", "yfinance",
    "tiktoken", "prophet", "tavily", "pandas_ta", "hdbscan", "thefuzz",
    "azure", "google", "docx", "PyPDF2", "kaleido", "plotly", "xlrd",
    "Levenshtein", "openpyxl",
}


class _StubModule(types.ModuleType):
    __path__ = []

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        # Capitalised -> a class (usable as a base class / annotation); else a callable.
        return type(name, (), {}) if name[:1].isupper() else (lambda *a, **k: None)


class _StubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        pass


class _StubFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _STUB_ROOTS:
            return importlib.machinery.ModuleSpec(fullname, _StubLoader(), is_package=True)
        return None


sys.meta_path.append(_StubFinder())
