import { Redirect } from 'expo-router';

/**
 * Entry route.
 *
 * Login is the only screen so far, so this hands straight over. When there is
 * a session to check, that decision belongs here rather than inside the form.
 */
export default function Index() {
  return <Redirect href="/login" />;
}
