# =====================================================
# GERADOR DE EMPENHO XML – SIAFI (NE001)
# Versão com layout profissional e formulários dinâmicos
# =====================================================

import streamlit as st
from xml.etree.ElementTree import Element, SubElement, ElementTree
import io

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(
    page_title="Gerador de Empenho XML – SIAFI",
    layout="centered"
)

# ---------------- CABEÇALHO ----------------
st.markdown(
    """
    <div style="display:flex; justify-content:center; margin-bottom:10px;">
        <img src="https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEj_FVD4fXy09Vp7bMnnbgnCWhwyVdeDWyltjZnQKBXyRKEd1C57np-0KiYGVo0gIJI76ksJBJ7mXs-Ybnqe4g-iK1gr5NLbWEAa8P-oObVAdNspC4ANsOhwmCrAlaQ1mw2jyMQaj6ZhJbhz/s1600/como-acessar-o-siafi-no-linux.png"
             style="max-width:220px; height:auto;">
    </div>
    <h1 style="text-align:center;">Gerador de Empenho XML</h1>
    <p style="text-align:center; color:#555;">Ferramenta para geração de XML conforme layout oficial do SIAFI</p>
    <hr>
    """,
    unsafe_allow_html=True
)

# ---------------- FORMULÁRIO ----------------
with st.form("form_empenho"):

    st.subheader("Dados Básicos")

    ug_executora = st.text_input(
        "UG Executora (6 dígitos)",
        max_chars=6
    )

    if ug_executora and (not ug_executora.isdigit() or len(ug_executora) != 6):
        st.error("A UG Executora deve conter exatamente 6 dígitos numéricos.")

    modalidade_dict = {
        "104 - Modalidade Não Se Aplica": "104",
        "001 - Concorrência": "001",
        "002 - Tomada de Preços": "002",
        "003 - Convite": "003",
        "004 - Concurso": "004",
        "005 - Leilão": "005",
        "006 - Pregão": "006",
        "007 - Diálogo Competitivo": "007",
        "008 - Dispensa de Licitação": "008",
        "009 - Inexigibilidade": "009",
    }

    modalidade = st.selectbox(
        "Modalidade / Amparo Legal",
        list(modalidade_dict.keys())
    )

    tipo_empenho_dict = {
        "1 - Ordinário": "1",
        "3 - Estimativo": "3",
        "5 - Global": "5",
    }

    tipo_empenho = st.selectbox(
        "Tipo de Empenho",
        list(tipo_empenho_dict.keys()),
        index=1
    )

    descricao_item = st.text_area(
        "Descrição do Item de Empenho",
        height=100
    )

    st.subheader("Conta Contábil")

    cod_conta_contabil = st.text_input(
        "Código da Conta Contábil",
        value="211110101"
    )

    st.subheader("PTRES para Passivo Anterior")

    ptres_padrao = ["171571", "171572", "171573"]

    ptres_selecionados = st.multiselect(
        "PTRES pré-selecionados",
        ptres_padrao,
        default=ptres_padrao
    )

    ptres_outros = st.text_input(
        "Outros PTRES (opcional – separar por vírgula)",
        placeholder="Ex: 123456, 654321"
    )

    gerar = st.form_submit_button("Gerar XML")

# ---------------- GERAÇÃO DO XML ----------------
if gerar:

    if not ug_executora or not descricao_item:
        st.error("Preencha todos os campos obrigatórios.")
    else:
        ptres_finais = ptres_selecionados.copy()

        if ptres_outros:
            for p in ptres_outros.split(","):
                p = p.strip()
                if p.isdigit() and len(p) == 6:
                    ptres_finais.append(p)

        root = Element("sb:empenho")

        SubElement(root, "sb:ugResponsavel").text = ug_executora
        SubElement(root, "codAmparoLegal").text = modalidade_dict[modalidade]
        SubElement(root, "codTipoEmpenho").text = tipo_empenho_dict[tipo_empenho]
        SubElement(root, "txtDescricao").text = descricao_item
        SubElement(root, "codContaContabil").text = cod_conta_contabil

        passivo = SubElement(root, "passivoAnterior")

        for pt in ptres_finais:
            SubElement(passivo, "ptres").text = pt

        xml_bytes = io.BytesIO()
        ElementTree(root).write(xml_bytes, encoding="utf-8", xml_declaration=True)

        st.success("XML gerado com sucesso!")

        st.download_button(
            label="📥 Baixar XML",
            data=xml_bytes.getvalue(),
            file_name="empenho_siafi.xml",
            mime="application/xml"
        )

# ---------------- RODAPÉ ----------------
st.markdown(
    """
    <hr>
    <p style="text-align:center; font-size:12px; color:#777;">
    Ferramenta colaborativa para a Administração Pública Federal • Uso orientativo • Não substitui validações do SIAFI
    </p>
    """,
    unsafe_allow_html=True
)

