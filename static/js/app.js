const CAMPO_MAP = {
  mt: {
    precio_unitario: "precio", iva: "iva", unidad: "unidad", stock: "stock",
    garantia_anos: "garantia", vida_util_anos: "vida", potencia_w: "potencia",
    eficiencia: "eficiencia", proveedor_id: "proveedor", ficha_url: "ficha",
    descripcion: "descripcion", params: "params",
  },
  ma: {
    proyecto_id: "proyecto", fecha_programada: "fp", fecha_realizado: "fr",
  },
};

// Prefijo corto de los ids de cada modal (modal-cliente -> cl-...)
const PREFIX_MODAL = {
  cliente: "cl", proveedor: "pr", empresa: "em", material: "mt",
  herramienta: "he", mant: "ma",
};

function prefijoDeModal(idModal) {
  const nombre = idModal.replace("modal-", "");
  return PREFIX_MODAL[nombre] || nombre;
}

function abrirModal(idModal, datos) {
  const modal = document.getElementById(idModal);
  const prefix = prefijoDeModal(idModal);
  const mapa = CAMPO_MAP[prefix] || {};
  const form = modal.querySelector("form");
  if (form) form.reset();

  const titulo = modal.querySelector(".modal-cab h3");
  if (titulo) {
    titulo.textContent = (datos && datos.id) ? "Editar registro" : "Nuevo registro";
  }

  if (datos && datos.id) {
    Object.keys(datos).forEach(clave => {
      const sufijo = mapa[clave] || clave;
      const el = modal.querySelector("#" + prefix + "-" + sufijo);
      if (!el) return;
      let valor = datos[clave];
      if (valor === null || valor === undefined) valor = "";
      if (el.tagName === "SELECT") {
        const ok = Array.from(el.options).some(o => String(o.value) === String(valor));
        el.value = ok ? valor : "";
      } else if (el.type !== "file") {
        el.value = valor;
      }
    });
  }

  // limpiar previsualizaciones de imagen
  modal.querySelectorAll(".preview-img").forEach(img => {
    img.style.display = "none";
    img.src = "";
  });
  modal.querySelectorAll("input[type=file]").forEach(inp => { inp.value = ""; });

  // caso especial: modal de mantenimiento con tareas
  if (prefix === "ma") {
    tareasActuales = [];
    if (datos && datos.tareas) {
      try { tareasActuales = JSON.parse(datos.tareas); } catch (e) { tareasActuales = []; }
    }
    const periodo = document.getElementById("ma-periodo");
    if (periodo && datos && datos.periodo) periodo.value = datos.periodo;
    if (typeof cargarTareas === "function") cargarTareas();
  }

  modal.classList.add("abierto");
}

function cerrarModal(idModal) {
  const modal = document.getElementById(idModal);
  if (modal) modal.classList.remove("abierto");
}

document.querySelectorAll(".modal").forEach(m => {
  m.addEventListener("click", (e) => {
    if (e.target === m) m.classList.remove("abierto");
  });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal.abierto").forEach(m => m.classList.remove("abierto"));
    cerrarLightbox();
  }
});

function previewImagen(input, idPreview) {
  const img = document.getElementById(idPreview);
  if (!img) return;
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      img.src = ev.target.result;
      img.style.display = "";
    };
    reader.readAsDataURL(input.files[0]);
  } else {
    img.style.display = "none";
  }
}

function abrirLightbox(src) {
  const lb = document.getElementById("lightbox");
  const img = document.getElementById("lightbox-img");
  img.src = src;
  lb.classList.add("abierto");
}
function cerrarLightbox() {
  const lb = document.getElementById("lightbox");
  if (lb) lb.classList.remove("abierto");
}

window.addEventListener("click", (e) => {
  const lb = document.getElementById("lightbox");
  if (lb && e.target === lb) cerrarLightbox();
});
