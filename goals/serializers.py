from django.db import transaction
from rest_framework import exceptions, serializers

from core.models import User
from core.serializes import UserSerializer

from goals.models import Board, BoardParticipant, Goal, GoalCategory, GoalComment


class BoardParticipantSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(required=True, choices=BoardParticipant.Role)
    user = serializers.SlugRelatedField(slug_field='username', queryset=User.objects.all())

    class Meta:
        model = BoardParticipant
        fields = '__all__'
        read_only_fields = ('id', 'created', 'updated', 'board')


class BoardCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Board
        read_only_fields = ('id', 'created', 'updated')
        fields = '__all__'

    def create(self, validated_data):
        user = validated_data.pop('user')
        board = Board.objects.create(**validated_data)
        BoardParticipant.objects.create(user=user, board=board, role=BoardParticipant.Role.owner)
        return board


class BoardSerializer(serializers.ModelSerializer):
    participants = BoardParticipantSerializer(many=True)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Board
        fields = '__all__'
        read_only_fields = ('id', 'created', 'updated')

    def update(self, instance: Board, validated_data):
        owner = validated_data.pop('user')
        participants_data = validated_data.pop('participants', [])

        existing_participants = instance.participants.exclude(user=owner)
        existing_participants = {participant.user_id: participant for participant in existing_participants}

        with transaction.atomic():
            new_participants = []
            participants_to_update = []

            for participant in participants_data:
                user_id = participant['user'].id

                if user_id in existing_participants:
                    participant_obj = existing_participants[user_id]
                    if participant['role'] != participant_obj.role:
                        participant_obj.role = participant['role']
                        participants_to_update.append(participant_obj)
                else:
                    new_participants.append(
                        BoardParticipant(board=instance, user=participant['user'], role=participant['role'])
                    )

            # Find participants to delete (existing participants not present in participants_data)
            participants_to_delete = set(existing_participants.keys()) - {
                participant['user'].id for participant in participants_data
            }
            BoardParticipant.objects.filter(board=instance, user_id__in=participants_to_delete).delete()

            # Create new participants
            BoardParticipant.objects.bulk_create(new_participants)

            # Update roles of existing participants
            BoardParticipant.objects.bulk_update(participants_to_update, ['role'])

            instance.title = validated_data['title']
            instance.save()

        return instance


class BoardListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    board = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = GoalCategory
        fields = '__all__'
        read_only_fields = ('id', 'created', 'updated', 'user', 'board')


class CategoryCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = GoalCategory
        read_only_fields = ('id', 'created', 'updated', 'user')
        fields = '__all__'

    def validate_title(self, value):
        if self.instance:
            queryset = GoalCategory.objects.exclude(pk=self.instance.pk)
        else:
            queryset = GoalCategory.objects.all()

        # Check if a category with the same title already exists
        if queryset.filter(title=value).exists():
            raise serializers.ValidationError('Category already exists.')

        # Check if the user has the required role in the board
        user = self.context['request'].user
        board = self.initial_data.get('board')

        if board is None:
            raise serializers.ValidationError('Board is required.')

        participant = BoardParticipant.objects.filter(board=board, user=user).first()

        if participant is None or participant.role not in [BoardParticipant.Role.owner, BoardParticipant.Role.writer]:
            raise serializers.ValidationError('You do not have permission to create a category.')

        return value


class GoalSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Goal
        fields = '__all__'
        read_only_fields = ('id', 'created', 'updated', 'user')


class GoalCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Goal
        read_only_fields = ('id', 'created', 'updated', 'user')
        fields = '__all__'

    def validate_category(self, category: GoalCategory) -> GoalCategory:
        if category.is_deleted:
            raise exceptions.NotFound('Category does not exist')

        user = self.context['request'].user

        if not category.board.participants.filter(
            user=user, role__in=[BoardParticipant.Role.owner, BoardParticipant.Role.writer]
        ).exists():
            raise exceptions.PermissionDenied('You do not have permission to create a goal in this category.')

        return category


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = GoalComment
        fields = '__all__'
        read_only_fields = ('id', 'created', 'updated', 'user')


class CommentCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = GoalComment
        read_only_fields = ('id', 'created', 'updated', 'user')
        fields = '__all__'

    def validate_goal(self, goal: Goal) -> Goal:
        if goal.status == Goal.Status.archived:
            raise exceptions.NotFound('Goal not exists')

        # Check if the user is a participant in the board with the goal
        if not BoardParticipant.objects.filter(
            user=self.context['request'].user,
            board__categories=goal.category,
            role__in=[BoardParticipant.Role.owner, BoardParticipant.Role.writer],
        ).exists():
            raise serializers.ValidationError('You do not have permission to comment on this goal.')

        return goal