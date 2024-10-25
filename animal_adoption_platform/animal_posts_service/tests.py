import unittest
from unittest.mock import patch, MagicMock
import animal_posts_pb2
import animal_posts_pb2_grpc
from server import AnimalService
from models import db, animal_posts


class TestAnimalService(unittest.TestCase):

    def setUp(self):
        self.server = AnimalService()
        self.context = MagicMock()

    #mock the database
    @patch('server.db')
    def test_create_animal_post(self, mock_db):
        #using the new data provided
        request = animal_posts_pb2.CreateAnimalRequest(
            title="Cat",
            description="A lost cat found near in the park",
            location="Valea Trandafirilor park",
            status="Found",
            images="cat_image.png"
        )

        #mock database behavior
        mock_db.session.execute.return_value = MagicMock()
        mock_db.session.commit.return_value = None
        mock_db.session.execute.return_value.fetchone.return_value = [1]
        response = self.server.CreateAnimalPost(request, self.context)
        self.assertEqual(response.postId, 1)
        self.assertEqual(response.message, "Post created successfully")

    @patch('server.db')
    def test_update_animal_post(self, mock_db):
        request = animal_posts_pb2.UpdateAnimalRequest(
            postId=1,
            title="Cat",
            description="A friendly cat",
            location="Home",
            status="Adopted",
            images="image2.png"
        )

        # mock fetching post
        mock_db.session.execute.return_value.fetchone.return_value = [1, "Dog", "A friendly dog", "Shelter",
                                                                      "Available", "image1.png"]

        response = self.server.UpdateAnimalPost(request, self.context)
        self.assertEqual(response.message, "Post updated successfully")

    @patch('server.db')
    def test_get_animals(self, mock_db):
        mock_db.session.execute.return_value.fetchall.return_value = [
            MagicMock(id=1, title="Dog", description="A friendly dog", location="Shelter", status="Available",
                      images="image1.png"),
            MagicMock(id=2, title="Cat", description="A friendly cat", location="Home", status="Adopted",
                      images="image2.png")
        ]

        request = animal_posts_pb2.Empty()
        response = self.server.GetAnimals(request, self.context)
        self.assertEqual(len(response.posts), 2)
        self.assertEqual(response.posts[0].title, "Dog")
        self.assertEqual(response.posts[1].title, "Cat")

    @patch('server.db')
    def test_delete_animal_post(self, mock_db):
        request = animal_posts_pb2.DeleteAnimalRequest(postId=1)

        # mock fetching post
        mock_db.session.execute.return_value.fetchone.return_value = [1, "Dog", "A friendly dog", "Shelter",
                                                                      "Available", "image1.png"]

        response = self.server.DeleteAnimalPost(request, self.context)
        self.assertEqual(response.message, "Post deleted successfully")

    @patch('server.db')
    def test_check_status(self, mock_db):
        request = animal_posts_pb2.Empty()
        response = self.server.CheckStatus(request, self.context)
        self.assertEqual(response.status, "Service is running")

    @patch('server.db')
    def test_get_load(self, mock_db):
        mock_db.session.query.return_value.count.return_value = 10

        request = animal_posts_pb2.Empty()
        response = self.server.GetLoad(request, self.context)
        self.assertEqual(response.load, 10)


if __name__ == '__main__':
    unittest.main()
