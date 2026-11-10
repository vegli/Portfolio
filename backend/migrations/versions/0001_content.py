"""Initial persistent game content schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('card_templates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('rarity', sa.Text(), nullable=False),
    sa.Column('min_difficulty', sa.SmallInteger(), nullable=False),
    sa.Column('max_difficulty', sa.SmallInteger(), nullable=False),
    sa.Column('positive_effect_budget', sa.Integer(), nullable=False),
    sa.Column('negative_effect_budget', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.CheckConstraint("rarity IN ('common', 'rare', 'epic')", name=op.f('ck_card_templates_rarity')),
    sa.CheckConstraint('min_difficulty BETWEEN 1 AND 5 AND max_difficulty BETWEEN min_difficulty AND 5', name=op.f('ck_card_templates_difficulty_range')),
    sa.CheckConstraint('positive_effect_budget >= 0 AND negative_effect_budget >= 0', name=op.f('ck_card_templates_budgets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_card_templates')),
    sa.UniqueConstraint('code', name=op.f('uq_card_templates_code'))
    )
    op.create_table('effects',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('trigger', sa.Text(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.Column('rarity', sa.Text(), nullable=False),
    sa.Column('cost', sa.Integer(), nullable=False),
    sa.Column('weight', sa.Integer(), nullable=False),
    sa.CheckConstraint("(trigger = 'correct' AND value > 0) OR (trigger = 'incorrect' AND value < 0)", name=op.f('ck_effects_trigger_value')),
    sa.CheckConstraint("rarity IN ('common', 'rare', 'epic')", name=op.f('ck_effects_rarity')),
    sa.CheckConstraint("trigger IN ('correct', 'incorrect')", name=op.f('ck_effects_trigger')),
    sa.CheckConstraint("type IN ('hp', 'score', 'time')", name=op.f('ck_effects_type')),
    sa.CheckConstraint('cost > 0 AND weight > 0', name=op.f('ck_effects_cost_weight')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_effects')),
    sa.UniqueConstraint('code', name=op.f('uq_effects_code'))
    )
    op.create_table('questions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('category', sa.Text(), nullable=False),
    sa.Column('difficulty', sa.SmallInteger(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("category IN ('backend_engineering', 'databases', 'networking', 'system_design', 'security', 'ddd', 'performance')", name=op.f('ck_questions_category')),
    sa.CheckConstraint('difficulty BETWEEN 1 AND 5', name=op.f('ck_questions_difficulty')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_questions'))
    )
    op.create_table('answer_options',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('question_id', sa.Uuid(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('is_correct', sa.Boolean(), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.CheckConstraint('position BETWEEN 1 AND 4', name=op.f('ck_answer_options_position')),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], name=op.f('fk_answer_options_question_id_questions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_answer_options')),
    sa.UniqueConstraint('question_id', 'position', name=op.f('uq_answer_options_question_id'))
    )
    op.create_index('uq_answer_options_correct_question', 'answer_options', ['question_id'], unique=True, postgresql_where=sa.text('is_correct'))
    op.create_table('card_template_effects',
    sa.Column('card_template_id', sa.Uuid(), nullable=False),
    sa.Column('effect_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['card_template_id'], ['card_templates.id'], name=op.f('fk_card_template_effects_card_template_id_card_templates'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['effect_id'], ['effects.id'], name=op.f('fk_card_template_effects_effect_id_effects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('card_template_id', 'effect_id', name=op.f('pk_card_template_effects'))
    )
    op.create_index(op.f('ix_card_template_effects_effect_id'), 'card_template_effects', ['effect_id'], unique=False)


def downgrade():
    op.drop_table('card_template_effects')
    op.drop_table('answer_options')
    op.drop_table('questions')
    op.drop_table('effects')
    op.drop_table('card_templates')
