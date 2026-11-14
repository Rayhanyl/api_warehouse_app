"""Skema Pydantic untuk pengaturan template layout dokumen cetak modular (Tahap 17 / Poin 10)."""

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import pydantic_optional_str, pydantic_required_str

DocumentType = Literal["GOODS_RECEIPT", "STOCK_TRANSFER", "PURCHASE_ORDER"]
LogoPosition = Literal["LEFT", "CENTER", "RIGHT"]
LogoSize = Literal["SMALL", "MEDIUM", "LARGE"]
PaperSize = Literal["A4", "LETTER", "F4"]
PaperOrientation = Literal["PORTRAIT", "LANDSCAPE"]
DocumentSectionKey = Literal["HEADER", "METADATA", "TABLE", "NOTES", "SIGNATURES"]

ALLOWED_SECTIONS: tuple[DocumentSectionKey, ...] = (
    "HEADER",
    "METADATA",
    "TABLE",
    "NOTES",
    "SIGNATURES",
)

ALLOWED_COLUMNS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "GOODS_RECEIPT": (
        "no",
        "sku_barcode",
        "item_name",
        "location",
        "qty_received",
        "uom",
        "notes",
    ),
    "STOCK_TRANSFER": (
        "no",
        "sku_barcode",
        "item_name",
        "uom",
        "qty_shipped",
        "qty_received",
        "variance",
    ),
    "PURCHASE_ORDER": (
        "no",
        "sku_barcode",
        "item_name",
        "uom",
        "qty_ordered",
        "qty_received",
        "notes",
    ),
}

_SAFE_LOGO_URL_REGEX = re.compile(
    r"^(/api/v1/document-templates/logos/logo-[a-f0-9]{32}\.(png|jpg|webp)|https?://[^\s]{4,240})$"
)


class TableColumnConfig(BaseModel):
    key: str = Field(..., min_length=1, max_length=40)
    label: str = Field(..., min_length=1, max_length=60)
    visible: bool = True

    @field_validator("key", "label", mode="before")
    @classmethod
    def _clean_text(cls, value: Any) -> Any:
        return pydantic_required_str(value, label="Kolom tabel")


class SignatureBlockConfig(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    subtitle: str | None = Field(default=None, max_length=120)
    placeholder: str = Field(..., min_length=1, max_length=120)

    @field_validator("title", "placeholder", mode="before")
    @classmethod
    def _clean_required(cls, value: Any) -> Any:
        return pydantic_required_str(value, label="Blok tanda tangan")

    @field_validator("subtitle", mode="before")
    @classmethod
    def _clean_subtitle(cls, value: Any) -> Any:
        return pydantic_optional_str(value)


class DocumentTemplateUpdate(BaseModel):
    document_title: str = Field(..., min_length=1, max_length=150)
    company_name: str = Field(..., min_length=1, max_length=150)
    company_address: str | None = Field(default=None, max_length=500)
    company_contact: str | None = Field(default=None, max_length=120)
    logo_url: str | None = Field(default=None, max_length=255)
    logo_position: LogoPosition = "LEFT"
    logo_size: LogoSize = "MEDIUM"
    header_notes: str | None = Field(default=None, max_length=1000)
    footer_notes: str | None = Field(default=None, max_length=1000)
    paper_size: PaperSize = "A4"
    orientation: PaperOrientation = "PORTRAIT"
    margin_mm: float = Field(default=12.0, ge=4.0, le=40.0)
    show_barcode: bool = True
    show_line_notes: bool = True
    show_company_contact: bool = True
    section_order: list[DocumentSectionKey] = Field(..., min_length=2, max_length=5)
    table_columns: list[TableColumnConfig] = Field(..., min_length=1, max_length=10)
    signature_layout: list[SignatureBlockConfig] = Field(..., min_length=0, max_length=4)

    @field_validator("document_title", "company_name", mode="before")
    @classmethod
    def _clean_required_fields(cls, value: Any) -> Any:
        return pydantic_required_str(value, label="Judul / Nama perusahaan")

    @field_validator(
        "company_address",
        "company_contact",
        "header_notes",
        "footer_notes",
        mode="before",
    )
    @classmethod
    def _clean_optional_fields(cls, value: Any) -> Any:
        return pydantic_optional_str(value)

    @field_validator("logo_url", mode="before")
    @classmethod
    def _validate_logo_url(cls, value: Any) -> Any:
        clean = pydantic_optional_str(value)
        if clean is None:
            return None
        if not isinstance(clean, str) or not _SAFE_LOGO_URL_REGEX.match(clean):
            raise ValueError(
                "URL logo harus berupa path unggahan resmi (/api/v1/document-templates/logos/...) atau URL http(s) yang valid."
            )
        return clean

    @model_validator(mode="after")
    def _validate_modular_layout(self) -> "DocumentTemplateUpdate":
        if len(set(self.section_order)) != len(self.section_order):
            raise ValueError("Urutan bagian dokumen tidak boleh memiliki duplikasi.")
        if "HEADER" not in self.section_order or "TABLE" not in self.section_order:
            raise ValueError(
                "Urutan bagian dokumen wajib menyertakan minimal bagian 'HEADER' dan 'TABLE'."
            )

        keys = [col.key for col in self.table_columns]
        if len(set(keys)) != len(keys):
            raise ValueError("Konfigurasi kolom tabel tidak boleh memiliki key ganda.")
        if not any(col.visible for col in self.table_columns):
            raise ValueError("Minimal 1 kolom tabel barang harus tetap ditampilkan.")

        self.margin_mm = round(float(self.margin_mm), 2)
        return self


class DocumentTemplateOut(BaseModel):
    id: int
    document_type: DocumentType
    document_title: str
    company_name: str
    company_address: str | None = None
    company_contact: str | None = None
    logo_url: str | None = None
    logo_position: LogoPosition
    logo_size: LogoSize
    header_notes: str | None = None
    footer_notes: str | None = None
    paper_size: PaperSize
    orientation: PaperOrientation
    margin_mm: float
    show_barcode: bool
    show_line_notes: bool
    show_company_contact: bool
    section_order: list[DocumentSectionKey]
    table_columns: list[TableColumnConfig]
    signature_layout: list[SignatureBlockConfig]
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime


class LogoUploadOut(BaseModel):
    logo_url: str
    filename: str
    content_type: str
    size_bytes: int
