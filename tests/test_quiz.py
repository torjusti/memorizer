from flask import url_for, session
from unittest.mock import patch
import random

from memorizer.database import db
from memorizer.models import Course, Exam, Question, Stats, User
from tests import DatabaseTestCase, MemorizerTestCase


def mock_user(registered=False, save=False):
        user = User()
        user.registered = registered
        user.name = "Name"
        user.username = "name"
        if save:
            db.session.add(user)
            db.session.commit()
        return user


def add_exam(course, name="T16"):
    exam = Exam(name, course.id)
    db.session.add(exam)
    db.session.commit()
    return exam


def add_course(code="TEST", name="Test Course"):
    course = Course(code, name)
    db.session.add(course)
    db.session.commit()
    return course


class QuizTest(DatabaseTestCase):
    def test_main(self):
        response = self.client.get('/')
        self.assert200(response)


class QuizRegisterTest(DatabaseTestCase):
    @patch('memorizer.views.quiz.get_user', return_value=mock_user())
    def test_register_get(self, mock_get_user):
        response = self.client.get('/register/')
        self.assert_200(response)

    @patch('memorizer.views.quiz.get_user', return_value=mock_user(registered=True))
    def test_register_registered(self, mock_get_user):
        response = self.client.get('/register/')
        self.assert_redirects(response, url_for('quiz.main'))

    @patch('memorizer.views.quiz.get_user', return_value=mock_user())
    def test_register_successful(self, mock_get_user):
        response = self.client.post('/register/', data=self.register_user_data())
        self.assert_redirects(response, url_for('quiz.main'))

    @patch('memorizer.views.quiz.get_user', return_value=mock_user())
    def test_register_fail(self, mock_get_user):
        response = self.client.post('/register/', data=self.register_user_data(username=""))
        self.assert_200(response)

    def register_user_data(self, name='Test User', username='Test', password='password1'):
        return {
            'name': name,
            'username': username,
            'password': password,
            'confirm': password
        }


class QuizLoginTest(DatabaseTestCase):
    @patch('memorizer.views.quiz.get_user', return_value=mock_user())
    def test_login_get(self, mock_get_user):
        response = self.client.get('/login/')
        self.assert_200(response)

    @patch('memorizer.views.quiz.get_user', return_value=mock_user(registered=True))
    def test_login_already_logged_in(self, mock_get_user):
        response = self.client.get('/login/')
        self.assert_redirects(response, url_for('quiz.main'))

    @patch('memorizer.views.quiz.get_user', return_value=mock_user())
    def test_login_successful(self, mock_get_user):
        username = 'Test1'
        password = 'password2'
        user = User()
        user.username = username
        user.password = password
        user.registered = True
        db.session.add(user)
        db.session.commit()

        response = self.client.post('/login/', data=self.login_user_data(username, password))
        self.assert_redirects(response, url_for('quiz.main'))

    @patch('memorizer.views.quiz.get_user', return_value=mock_user())
    def test_login_fail(self, mock_get_user):
        username = 'username1'
        password = 'pass1'
        user = User()
        user.username = username
        user.password = password
        user.registered = True
        db.session.add(user)
        db.session.commit()

        response = self.client.post('/login/', data=self.login_user_data(username, 'pass2'))
        self.assert_200(response)

    def login_user_data(self, username='Test', password='password1'):
        return {
            'username': username,
            'password': password
        }


class QuizLogoutTest(MemorizerTestCase):
    def test_login_logged_in(self):
        with self.client.session_transaction() as sess:
            print(sess.__dict__)
            sess['user'] = 123
        response = self.client.get('/logout/')
        self.assert_redirects(response, url_for('quiz.main'))
        self.assertNotIn('user', session)

    def test_login_logged_out(self):
        response = self.client.get('/logout/')
        self.assert_redirects(response, url_for('quiz.main'))


class RenderViewTest(MemorizerTestCase):
    def test_tips(self):
        response = self.client.get('/tips/')
        self.assert200(response)


class ResetStatsTest(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User()
        db.session.add(self.user)
        db.session.commit()
        # Add 5 courses with 3 exams each with stats
        for course_n in range(5):
            course = Course("TEST%d" % course_n, "Test Course")
            db.session.add(course)
            db.session.commit()
            for exam_n in range(3):
                exam = Exam("V%d" % exam_n, course.id)
                db.session.add(exam)
                db.session.commit()
                question = Question(exam_id=exam.id, type=Question.BOOLEAN, text="Test Question", correct=True)
                db.session.add(question)
                db.session.commit()
                for stats_n in range(2):
                    stats = Stats(self.user, question, random.choice([True, False]))
                    db.session.add(stats)
        db.session.commit()

    def test_reset_exam(self):
        course = Course.query.all()[2]
        exam = course.exams[1]

        stats_query = Stats.exam(self.user, course.code, exam.name).with_entities(Stats.id).subquery()
        stats_count_all = Stats.query.filter_by(reset=False).count()
        stats_count = Stats.query.filter(Stats.id.in_(stats_query)).count()
        self.assertTrue(stats_count > 0)

        with patch('memorizer.views.quiz.get_user', return_value=self.user):
            response = self.client.get('/reset/{course}/{exam}/'.format(course=course.code, exam=exam.name))
            self.assert_redirects(response, url_for('quiz.exam', course=course.code, exam=exam.name))

        stats_count_all_after = Stats.query.filter_by(reset=False).count()
        stats_count_after = Stats.query.filter(Stats.id.in_(stats_query)).count()
        self.assertTrue(stats_count_after == 0)
        self.assertEqual(stats_count_all_after, stats_count_all - stats_count)

    def test_reset_course(self):
        course = Course.query.all()[1]

        stats_query = Stats.course(self.user, course.code).with_entities(Stats.id).subquery()
        stats_count_all = Stats.query.filter_by(reset=False).count()
        stats_count = Stats.query.filter(Stats.id.in_(stats_query)).count()
        self.assertTrue(stats_count > 0)

        with patch('memorizer.views.quiz.get_user', return_value=self.user):
            response = self.client.get('/reset/{course}/'.format(course=course.code))
            self.assert_redirects(response, url_for('quiz.course', course=course.code))

        stats_count_all_after = Stats.query.filter_by(reset=False).count()
        stats_count_after = Stats.query.filter(Stats.id.in_(stats_query)).count()
        self.assertTrue(stats_count_after == 0)
        self.assertEqual(stats_count_all_after, stats_count_all - stats_count)


class RedirectTest(DatabaseTestCase):
    @patch('memorizer.views.quiz.utils.random_id', return_value=1)
    def test_course(self, random_patch):
        course = Course(code='TEST1', name='Course')
        db.session.add(course)
        db.session.commit()
        response = self.client.get('/%s/' % course.code)
        self.assert_redirects(
            response, url_for('quiz.question_course', course_code=course.code, id=1)
        )

    @patch('memorizer.views.quiz.utils.random_id', return_value=1)
    def test_exam(self, random_patch):
        course = Course(code='TEST1', name='Course')
        db.session.add(course)
        db.session.commit()

        exam = Exam("H1", course.id)
        db.session.add(exam)
        db.session.commit()

        response = self.client.get('/%s/%s/' % (course.code, exam.name))
        self.assert_redirects(
            response, url_for('quiz.question_exam', course_code=course.code, exam_name=exam.name, id=1)
        )


class QuestionTest(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        course = add_course()
        exam = add_exam(course)
        # self.multiple = Question(exam_id=exam.id, type=Question.MULTIPLE, text="Test Question")
        self.boolean = Question(exam_id=exam.id, type=Question.BOOLEAN, text="Test Question", correct=True)
        db.session.add(self.boolean)
        db.session.commit()

    def test_view(self):
        question = self.boolean
        user = mock_user(save=True)
        with patch('memorizer.utils.get_user', return_value=user):
            response = self.client.get(url_for('quiz.question_course', course_code=question.course.code, id=1))
        self.assert200(response)

    def test_answer(self):
        question = self.boolean
        url = url_for('quiz.question_course', course_code=question.course.code, id=1)
        response = self.post_answer(url)
        self.assert200(response)

    @patch('memorizer.utils.get_user')
    @patch('memorizer.views.quiz.get_user')
    def post_answer(self, url, user_mock, user_mock2):
        user = mock_user(save=True)
        user_mock.return_value = user
        user_mock2.return_value = user
        answer = 'true'
        response = self.client.post(url, data={'answer': answer})
        return response