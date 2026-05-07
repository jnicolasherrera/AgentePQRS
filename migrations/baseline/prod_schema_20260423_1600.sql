--
-- PostgreSQL database dump
--

\restrict OSs2RThdUhnOJxiLreej7WM6pGSbS0iCKaabjwF3c6kGVPPvliOSrHF47wWALeO

-- Dumped from database version 15.17
-- Dumped by pg_dump version 15.17

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: update_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log_respuestas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log_respuestas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    caso_id uuid,
    usuario_id uuid,
    accion character varying(30) NOT NULL,
    lote_id uuid,
    ip_origen inet,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: clientes_tenant; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clientes_tenant (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nombre character varying(255) NOT NULL,
    dominio character varying(255) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: config_buzones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.config_buzones (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    cliente_id uuid NOT NULL,
    email_buzon character varying(255) NOT NULL,
    azure_folder_id character varying(500) NOT NULL,
    azure_client_id character varying(255),
    azure_client_secret character varying(255),
    azure_tenant_id character varying(255),
    is_active boolean DEFAULT true,
    last_sync timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    proveedor character varying(50) DEFAULT 'OUTLOOK'::character varying,
    zoho_refresh_token text,
    zoho_account_id character varying(255),
    sharepoint_site_id character varying(255),
    sharepoint_base_folder character varying(500)
);


--
-- Name: plantillas_respuesta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plantillas_respuesta (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cliente_id uuid,
    problematica character varying(100) NOT NULL,
    contexto text,
    cuerpo text NOT NULL,
    keywords text[],
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pqrs_adjuntos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pqrs_adjuntos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    caso_id uuid NOT NULL,
    nombre_archivo character varying(255) NOT NULL,
    storage_path character varying(500) NOT NULL,
    content_type character varying(100),
    tamano_bytes bigint,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    cliente_id uuid NOT NULL,
    es_reply boolean DEFAULT false
);


--
-- Name: pqrs_casos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pqrs_casos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    cliente_id uuid NOT NULL,
    email_origen character varying(255) NOT NULL,
    asunto character varying(500) NOT NULL,
    cuerpo text,
    estado character varying(50) DEFAULT 'ABIERTO'::character varying,
    nivel_prioridad character varying(50) DEFAULT 'NORMAL'::character varying,
    fecha_recibido timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento timestamp with time zone,
    tipo_caso character varying(100),
    external_msg_id text,
    asignado_a uuid,
    fecha_asignacion timestamp with time zone,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    alerta_2h_enviada boolean DEFAULT false,
    borrador_respuesta text,
    borrador_estado character varying(20) DEFAULT 'SIN_PLANTILLA'::character varying,
    problematica_detectada character varying(100),
    plantilla_id uuid,
    aprobado_por uuid,
    aprobado_at timestamp with time zone,
    enviado_at timestamp with time zone,
    acuse_enviado boolean DEFAULT false,
    numero_radicado character varying(30),
    es_pqrs boolean DEFAULT true,
    reply_adjunto_ids uuid[] DEFAULT '{}'::uuid[],
    texto_respuesta_final text,
    borrador_ia_original text,
    edit_ratio double precision DEFAULT 0
);

ALTER TABLE ONLY public.pqrs_casos FORCE ROW LEVEL SECURITY;


--
-- Name: pqrs_clasificacion_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pqrs_clasificacion_feedback (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    caso_id uuid NOT NULL,
    cliente_id uuid NOT NULL,
    clasificacion_original character varying(20),
    clasificacion_correcta character varying(20),
    es_pqrs boolean DEFAULT true NOT NULL,
    marcado_por uuid,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: pqrs_comentarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pqrs_comentarios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    caso_id uuid NOT NULL,
    usuario_id uuid,
    comentario text NOT NULL,
    tipo_evento character varying(50) DEFAULT 'COMENTARIO'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    cliente_id uuid NOT NULL
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    cliente_id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    nombre character varying(255) NOT NULL,
    rol character varying(50) DEFAULT 'abogado'::character varying,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    debe_cambiar_password boolean DEFAULT false
);

ALTER TABLE ONLY public.usuarios FORCE ROW LEVEL SECURITY;


--
-- Name: audit_log_respuestas audit_log_respuestas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log_respuestas
    ADD CONSTRAINT audit_log_respuestas_pkey PRIMARY KEY (id);


--
-- Name: clientes_tenant clientes_tenant_dominio_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes_tenant
    ADD CONSTRAINT clientes_tenant_dominio_key UNIQUE (dominio);


--
-- Name: clientes_tenant clientes_tenant_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes_tenant
    ADD CONSTRAINT clientes_tenant_pkey PRIMARY KEY (id);


--
-- Name: config_buzones config_buzones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_buzones
    ADD CONSTRAINT config_buzones_pkey PRIMARY KEY (id);


--
-- Name: plantillas_respuesta plantillas_respuesta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plantillas_respuesta
    ADD CONSTRAINT plantillas_respuesta_pkey PRIMARY KEY (id);


--
-- Name: pqrs_adjuntos pqrs_adjuntos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_adjuntos
    ADD CONSTRAINT pqrs_adjuntos_pkey PRIMARY KEY (id);


--
-- Name: pqrs_casos pqrs_casos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_casos
    ADD CONSTRAINT pqrs_casos_pkey PRIMARY KEY (id);


--
-- Name: pqrs_clasificacion_feedback pqrs_clasificacion_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_clasificacion_feedback
    ADD CONSTRAINT pqrs_clasificacion_feedback_pkey PRIMARY KEY (id);


--
-- Name: pqrs_comentarios pqrs_comentarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_comentarios
    ADD CONSTRAINT pqrs_comentarios_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: idx_adjuntos_caso_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_adjuntos_caso_id ON public.pqrs_adjuntos USING btree (caso_id);


--
-- Name: idx_audit_caso; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_caso ON public.audit_log_respuestas USING btree (caso_id);


--
-- Name: idx_audit_lote; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_lote ON public.audit_log_respuestas USING btree (lote_id);


--
-- Name: idx_audit_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_usuario ON public.audit_log_respuestas USING btree (usuario_id, created_at DESC);


--
-- Name: idx_casos_asignado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_casos_asignado ON public.pqrs_casos USING btree (asignado_a) WHERE (asignado_a IS NOT NULL);


--
-- Name: idx_casos_dedup_natural; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_casos_dedup_natural ON public.pqrs_casos USING btree (cliente_id, email_origen, date_trunc('hour'::text, (fecha_recibido AT TIME ZONE 'UTC'::text))) WHERE ((external_msg_id IS NULL) OR (external_msg_id = ''::text));


--
-- Name: idx_casos_external_msg; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_casos_external_msg ON public.pqrs_casos USING btree (cliente_id, external_msg_id) WHERE (external_msg_id IS NOT NULL);


--
-- Name: idx_comentarios_caso_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comentarios_caso_id ON public.pqrs_comentarios USING btree (caso_id);


--
-- Name: idx_plantillas_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_plantillas_tenant ON public.plantillas_respuesta USING btree (cliente_id, problematica);


--
-- Name: idx_pqrs_borrador_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pqrs_borrador_estado ON public.pqrs_casos USING btree (cliente_id, borrador_estado) WHERE ((borrador_estado)::text = 'PENDIENTE'::text);


--
-- Name: idx_pqrs_cliente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pqrs_cliente_id ON public.pqrs_casos USING btree (cliente_id);


--
-- Name: idx_pqrs_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pqrs_estado ON public.pqrs_casos USING btree (estado);


--
-- Name: idx_pqrs_radicado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pqrs_radicado ON public.pqrs_casos USING btree (numero_radicado) WHERE (numero_radicado IS NOT NULL);


--
-- Name: idx_pqrs_tutela_alerta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pqrs_tutela_alerta ON public.pqrs_casos USING btree (tipo_caso, alerta_2h_enviada, fecha_recibido) WHERE (((tipo_caso)::text = 'TUTELA'::text) AND (alerta_2h_enviada = false));


--
-- Name: idx_usuarios_cliente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_usuarios_cliente_id ON public.usuarios USING btree (cliente_id);


--
-- Name: pqrs_casos trg_casos_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_casos_updated_at BEFORE UPDATE ON public.pqrs_casos FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


--
-- Name: audit_log_respuestas audit_log_respuestas_caso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log_respuestas
    ADD CONSTRAINT audit_log_respuestas_caso_id_fkey FOREIGN KEY (caso_id) REFERENCES public.pqrs_casos(id);


--
-- Name: audit_log_respuestas audit_log_respuestas_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log_respuestas
    ADD CONSTRAINT audit_log_respuestas_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: config_buzones config_buzones_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_buzones
    ADD CONSTRAINT config_buzones_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes_tenant(id) ON DELETE CASCADE;


--
-- Name: plantillas_respuesta plantillas_respuesta_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plantillas_respuesta
    ADD CONSTRAINT plantillas_respuesta_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes_tenant(id) ON DELETE CASCADE;


--
-- Name: pqrs_adjuntos pqrs_adjuntos_caso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_adjuntos
    ADD CONSTRAINT pqrs_adjuntos_caso_id_fkey FOREIGN KEY (caso_id) REFERENCES public.pqrs_casos(id) ON DELETE CASCADE;


--
-- Name: pqrs_adjuntos pqrs_adjuntos_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_adjuntos
    ADD CONSTRAINT pqrs_adjuntos_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes_tenant(id) ON DELETE CASCADE;


--
-- Name: pqrs_casos pqrs_casos_aprobado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_casos
    ADD CONSTRAINT pqrs_casos_aprobado_por_fkey FOREIGN KEY (aprobado_por) REFERENCES public.usuarios(id);


--
-- Name: pqrs_casos pqrs_casos_asignado_a_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_casos
    ADD CONSTRAINT pqrs_casos_asignado_a_fkey FOREIGN KEY (asignado_a) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: pqrs_casos pqrs_casos_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_casos
    ADD CONSTRAINT pqrs_casos_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes_tenant(id) ON DELETE CASCADE;


--
-- Name: pqrs_casos pqrs_casos_plantilla_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_casos
    ADD CONSTRAINT pqrs_casos_plantilla_id_fkey FOREIGN KEY (plantilla_id) REFERENCES public.plantillas_respuesta(id);


--
-- Name: pqrs_clasificacion_feedback pqrs_clasificacion_feedback_caso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_clasificacion_feedback
    ADD CONSTRAINT pqrs_clasificacion_feedback_caso_id_fkey FOREIGN KEY (caso_id) REFERENCES public.pqrs_casos(id);


--
-- Name: pqrs_comentarios pqrs_comentarios_caso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_comentarios
    ADD CONSTRAINT pqrs_comentarios_caso_id_fkey FOREIGN KEY (caso_id) REFERENCES public.pqrs_casos(id) ON DELETE CASCADE;


--
-- Name: pqrs_comentarios pqrs_comentarios_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_comentarios
    ADD CONSTRAINT pqrs_comentarios_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes_tenant(id) ON DELETE CASCADE;


--
-- Name: pqrs_comentarios pqrs_comentarios_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pqrs_comentarios
    ADD CONSTRAINT pqrs_comentarios_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: usuarios usuarios_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes_tenant(id) ON DELETE CASCADE;


--
-- Name: config_buzones; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.config_buzones ENABLE ROW LEVEL SECURITY;

--
-- Name: pqrs_adjuntos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.pqrs_adjuntos ENABLE ROW LEVEL SECURITY;

--
-- Name: pqrs_casos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.pqrs_casos ENABLE ROW LEVEL SECURITY;

--
-- Name: pqrs_comentarios; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.pqrs_comentarios ENABLE ROW LEVEL SECURITY;

--
-- Name: pqrs_adjuntos tenant_isolation_adjuntos_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_adjuntos_policy ON public.pqrs_adjuntos USING (((cliente_id = (current_setting('app.current_tenant_id'::text, true))::uuid) OR (current_setting('app.is_superuser'::text, true) = 'true'::text)));


--
-- Name: pqrs_comentarios tenant_isolation_comentarios_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_comentarios_policy ON public.pqrs_comentarios USING (((cliente_id = (current_setting('app.current_tenant_id'::text, true))::uuid) OR (current_setting('app.is_superuser'::text, true) = 'true'::text)));


--
-- Name: config_buzones tenant_isolation_config_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_config_policy ON public.config_buzones USING (((cliente_id = (current_setting('app.current_tenant_id'::text, true))::uuid) OR (current_setting('app.is_superuser'::text, true) = 'true'::text)));


--
-- Name: pqrs_casos tenant_isolation_pqrs_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_pqrs_policy ON public.pqrs_casos USING (((cliente_id = (current_setting('app.current_tenant_id'::text, true))::uuid) OR (current_setting('app.is_superuser'::text, true) = 'true'::text)));


--
-- Name: usuarios tenant_isolation_usuarios_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_usuarios_policy ON public.usuarios USING (((cliente_id = (current_setting('app.current_tenant_id'::text, true))::uuid) OR (current_setting('app.is_superuser'::text, true) = 'true'::text)));


--
-- Name: usuarios; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.usuarios ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict OSs2RThdUhnOJxiLreej7WM6pGSbS0iCKaabjwF3c6kGVPPvliOSrHF47wWALeO

