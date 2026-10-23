"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-20 07:52:41.277815
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector extension must exist before any VECTOR column is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('chat_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('visitor_id', sa.String(length=64), nullable=True),
    sa.Column('language', sa.String(length=10), nullable=False),
    sa.Column('page_url', sa.String(length=1000), nullable=True),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.Column('message_count', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_started_at'), 'chat_sessions', ['started_at'], unique=False)
    op.create_index(op.f('ix_chat_sessions_visitor_id'), 'chat_sessions', ['visitor_id'], unique=False)
    op.create_table('departments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=60), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_departments_slug'), 'departments', ['slug'], unique=True)
    op.create_table('faqs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=60), nullable=True),
    sa.Column('department_id', sa.Integer(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('hits', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sources', sa.JSON(), nullable=False),
    sa.Column('intent', sa.String(length=30), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('answered', sa.Boolean(), nullable=False),
    sa.Column('answer_source', sa.String(length=20), nullable=True),
    sa.Column('model', sa.String(length=60), nullable=True),
    sa.Column('prompt_tokens', sa.Integer(), nullable=False),
    sa.Column('completion_tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_created_at'), 'messages', ['created_at'], unique=False)
    op.create_index(op.f('ix_messages_session_id'), 'messages', ['session_id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=30), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity', sa.String(length=60), nullable=False),
    sa.Column('entity_id', sa.String(length=60), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('filename', sa.String(length=300), nullable=True),
    sa.Column('file_path', sa.String(length=500), nullable=True),
    sa.Column('source_url', sa.String(length=1000), nullable=True),
    sa.Column('mime_type', sa.String(length=120), nullable=True),
    sa.Column('doc_type', sa.String(length=40), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=True),
    sa.Column('academic_year', sa.String(length=20), nullable=True),
    sa.Column('valid_from', sa.Date(), nullable=True),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('num_pages', sa.Integer(), nullable=False),
    sa.Column('num_chunks', sa.Integer(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_academic_year'), 'documents', ['academic_year'], unique=False)
    op.create_index(op.f('ix_documents_status'), 'documents', ['status'], unique=False)
    op.create_table('feedback',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('message_id')
    )
    op.create_table('tickets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_code', sa.String(length=30), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=True),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tickets_category'), 'tickets', ['category'], unique=False)
    op.create_index(op.f('ix_tickets_created_at'), 'tickets', ['created_at'], unique=False)
    op.create_index(op.f('ix_tickets_department_id'), 'tickets', ['department_id'], unique=False)
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'], unique=False)
    op.create_index(op.f('ix_tickets_ticket_code'), 'tickets', ['ticket_code'], unique=True)
    op.create_table('chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('page_no', sa.Integer(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('simple', content)", persisted=True), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chunks_document_id'), 'chunks', ['document_id'], unique=False)
    op.create_index('ix_chunks_embedding_hnsw', 'chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_chunks_tsv', 'chunks', ['tsv'], unique=False, postgresql_using='gin')
    op.create_table('ticket_updates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status_from', sa.String(length=20), nullable=True),
    sa.Column('status_to', sa.String(length=20), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_updates_ticket_id'), 'ticket_updates', ['ticket_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_ticket_updates_ticket_id'), table_name='ticket_updates')
    op.drop_table('ticket_updates')
    op.drop_index('ix_chunks_tsv', table_name='chunks', postgresql_using='gin')
    op.drop_index('ix_chunks_embedding_hnsw', table_name='chunks', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index(op.f('ix_chunks_document_id'), table_name='chunks')
    op.drop_table('chunks')
    op.drop_index(op.f('ix_tickets_ticket_code'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_status'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_department_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_created_at'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_category'), table_name='tickets')
    op.drop_table('tickets')
    op.drop_table('feedback')
    op.drop_index(op.f('ix_documents_status'), table_name='documents')
    op.drop_index(op.f('ix_documents_academic_year'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_messages_session_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_created_at'), table_name='messages')
    op.drop_table('messages')
    op.drop_table('faqs')
    op.drop_index(op.f('ix_departments_slug'), table_name='departments')
    op.drop_table('departments')
    op.drop_index(op.f('ix_chat_sessions_visitor_id'), table_name='chat_sessions')
    op.drop_index(op.f('ix_chat_sessions_started_at'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
    # ### end Alembic commands ###
